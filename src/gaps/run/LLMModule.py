import time
import json
import threading
import subprocess as subp
import xml.etree.ElementTree as ET
import os
import re


class LLMThread(threading.Thread):
    def __init__(
        self,
        apk_path,
        instructions_dir,
        target_method,
        activity,
        _id,
        package_name,
        target_path,
    ):
        self.apk_path = apk_path
        self.activity = activity
        self._id = _id
        self.instructions_dir = instructions_dir
        self.target_method = target_method
        self.package_name = package_name
        self.target_path = target_path
        self._stop_event = threading.Event()
        threading.Thread.__init__(self)

    def get_ui_hierarchy(self):
        # dump hierarchy
        subp.run(
            "adb shell uiautomator dump /data/local/tmp/window_dump.xml",
            shell=True,
            stdout=subp.DEVNULL,
            stderr=subp.DEVNULL,
        )
        res = subp.run(
            "adb shell cat /data/local/tmp/window_dump.xml",
            shell=True,
            capture_output=True,
            text=True,
        )
        xml_content = res.stdout
        if (
            not xml_content
            or "UI hierchary dumped to" not in xml_content
            and not xml_content.strip().startswith("<?xml")
        ):
            return []

        xml_start = xml_content.find("<?xml")
        if xml_start != -1:
            xml_content = xml_content[xml_start:]
        else:
            return []

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError:
            return []

        elements = []
        element_idx = 0
        for node in root.iter("node"):
            if node.attrib.get("package") == "com.android.systemui":
                continue
            clickable = node.attrib.get("clickable") == "true"
            scrollable = node.attrib.get("scrollable") == "true"
            is_edit_text = "EditText" in node.attrib.get("class", "")

            if clickable or scrollable or is_edit_text:
                resource_id = node.attrib.get("resource-id", "")
                text = node.attrib.get("text", "")
                content_desc = node.attrib.get("content-desc", "")
                bounds = node.attrib.get("bounds", "")
                class_name = node.attrib.get("class", "")

                if bounds == "[0,0][0,0]":
                    continue

                info = f"Index: {element_idx}, Class: {class_name}, Text: {text}, Desc: {content_desc}, Id: {resource_id}"
                action_type = (
                    "text"
                    if is_edit_text
                    else ("click" if clickable else "swipe")
                )
                elements.append(
                    {
                        "index": element_idx,
                        "info": info,
                        "resource_id": resource_id,
                        "action_type": action_type,
                        "bounds": bounds,
                        "class_name": class_name,
                    }
                )
                element_idx += 1
        return elements

    def query_llm(
        self,
        class_name,
        method_name,
        elements,
        curr_activity,
        past_actions,
        error_feedback="",
    ):
        import openai

        # Initialize OpenAI client
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        elements_text = "\n".join([e["info"] for e in elements])
        history_text = (
            "\n".join([f"- {act}" for act in past_actions])
            if past_actions
            else "None"
        )
        path_text = (
            "\n".join([str(p) for p in self.target_path])
            if self.target_path
            else "Not provided"
        )

        prompt = f"""You are an Android UI testing agent navigating an app to find a specific target.
Your objective is to reach class "{class_name}" and method "{method_name}".
The planned execution path provided by static analysis is:
{path_text}

You are currently on the Android activity: {curr_activity}.
Here are the interactable elements on the current screen:
{elements_text}

Past actions taken in this session (avoid repeating failed loops):
{history_text}

{error_feedback}

Choose one element to interact with to get closer to the objective.
You MUST respond with a strictly valid JSON object using this schema:
{{
    "action": "CLICK" | "TYPE" | "SWIPE" | "BACK",
    "index": <integer reference to the element index, or -1 if BACK>,
    "text": "<only required if action is TYPE, otherwise empty string>"
}}
Output nothing but the JSON object. Do not wrap it in markdown block quotes.
"""
        max_retries = 3
        for _ in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model="gpt-5.2",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a specialized JSON-only Android UI testing assistant.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )
                content = response.choices[0].message.content.strip()
                if content.startswith("```json"):
                    content = content[7:-3].strip()
                elif content.startswith("```"):
                    content = content[3:-3].strip()
                return json.loads(content)
            except Exception as e:
                print(f"OpenAI API Error: {e}")
                time.sleep(2)
        return {"action": "BACK", "index": -1, "text": ""}

    def execute_action(self, action_json, elements, curr_activity):
        cmd = action_json.get("action", "").upper()

        if cmd == "BACK":
            subp.run("adb shell input keyevent 4", shell=True)
            return "BACK", ""

        index = action_json.get("index", -1)
        if index == -1:
            return "INVALID", "No valid index provided."

        element = next((e for e in elements if e["index"] == index), None)
        if not element:
            return (
                "INVALID",
                f"Element with index {index} not found on screen.",
            )

        resource_id = element["resource_id"]
        if resource_id and "/" in resource_id:
            res_id_short = resource_id.split("/")[1]
        else:
            res_id_short = str(element["bounds"])

        action_log = ""
        action_summary = ""

        if cmd == "CLICK":
            bounds = element["bounds"]
            if bounds:
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    subp.run(f"adb shell input tap {x} {y}", shell=True)
            action_log = f"click {self.package_name}:id/{res_id_short}"
            action_summary = f"CLICKED index {index}"

        elif cmd == "TYPE":
            text = action_json.get("text", "")
            bounds = element["bounds"]
            if bounds:
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    subp.run(f"adb shell input tap {x} {y}", shell=True)
                    time.sleep(0.5)
                    text_escaped = text.replace(" ", r"\ ")
                    subp.run(
                        f'adb shell input keycombination 113 29 && adb shell input keyevent 67 && adb shell input text "{text_escaped}"',
                        shell=True,
                    )
            action_log = f"text {self.package_name}:id/{res_id_short} {text}"
            action_summary = f"TYPED '{text}' into index {index}"

        elif cmd == "SWIPE":
            bounds = element["bounds"]
            if bounds:
                m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)
                if m:
                    x = (int(m.group(1)) + int(m.group(3))) // 2
                    y = (int(m.group(2)) + int(m.group(4))) // 2
                    subp.run(
                        f"adb shell input swipe {x} {y} {x} {max(10, y - 400)}",
                        shell=True,
                    )
            else:
                subp.run("adb shell input swipe 500 1000 500 300", shell=True)
            action_log = f"swipe {self.package_name}:id/{res_id_short}"
            action_summary = f"SWIPED on index {index}"

        if action_log:
            self.save_memory(curr_activity, action_log)
            return "SUCCESS", action_summary

        return "UNKNOWN", "Unknown action command"

    def save_memory(self, curr_activity, action_log):
        memory_file = os.path.join(
            self.instructions_dir, "activity_memory.json"
        )
        try:
            time.sleep(1)
            get_current_focus = subp.Popen(
                "adb shell dumpsys window | grep mCurrentFocus",
                shell=True,
                stdout=subp.PIPE,
            )
            communicate = get_current_focus.communicate()
            if not communicate[0]:
                return
            new_activity = (
                communicate[0].decode().strip().split("/")[-1].replace("}", "")
            )

            if (
                curr_activity != new_activity
                and curr_activity
                and new_activity
            ):
                data = {}
                if os.path.exists(memory_file):
                    with open(memory_file, "r") as f:
                        data = json.load(f)

                if curr_activity not in data:
                    data[curr_activity] = {}
                if new_activity not in data[curr_activity]:
                    data[curr_activity][new_activity] = []

                events_list = [action_log]
                if events_list not in data[curr_activity][new_activity]:
                    data[curr_activity][new_activity].append(events_list)

                with open(memory_file, "w") as f:
                    json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving memory: {e}")

    def run(self):
        class_name, method_name = self.target_method.split(";->")
        class_name = class_name[1:].replace("/", ".")
        method_name = method_name.split("(")[0]
        if "<init>" == method_name:
            method_name = "init"

        attempts = 0
        past_actions = []
        error_feedback = ""

        while not self._stop_event.is_set() and attempts < 15:
            get_current_focus = subp.Popen(
                "adb shell dumpsys window | grep mCurrentFocus",
                shell=True,
                stdout=subp.PIPE,
            )
            communicate = get_current_focus.communicate()
            if not communicate[0]:
                time.sleep(1)
                attempts += 1
                continue
            curr_activity = (
                communicate[0].decode().strip().split("/")[-1].replace("}", "")
            )

            elements = self.get_ui_hierarchy()
            if not elements:
                time.sleep(1)
                attempts += 1
                continue

            action_json = self.query_llm(
                class_name,
                method_name,
                elements,
                curr_activity,
                past_actions,
                error_feedback,
            )
            print(f"[{curr_activity}] LLM Action JSON: {action_json}")
            status, msg = self.execute_action(
                action_json, elements, curr_activity
            )

            if status == "INVALID":
                error_feedback = f"Error from last action: {msg}. Please select a valid index from the list."
                print(f"[!] {error_feedback}")
            else:
                error_feedback = ""
                if status == "SUCCESS":
                    past_actions.append(msg)
                    if len(past_actions) > 5:
                        past_actions.pop(0)

            time.sleep(2)
            attempts += 1

    def stop(self):
        self._stop_event.set()
