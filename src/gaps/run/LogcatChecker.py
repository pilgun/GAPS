import threading
import subprocess as subp

from . import utils


class LogcatChecker(threading.Thread):
    def __init__(self, json_paths, methods_por):
        super().__init__()
        self.json_paths = json_paths
        self.methods_por = methods_por
        self._stop_event = threading.Event()
        self.process = None

    def run(self):
        methods = list(self.json_paths.keys())
        java_methods = {}

        for method in methods:
            java_method = utils.to_java_signature(method)
            java_methods[java_method] = method

        self.process = subp.Popen(
            ["adb", "logcat", "-s", "GAPS"],
            stdout=subp.PIPE,
            stderr=subp.DEVNULL,
            text=True,
        )

        while not self._stop_event.is_set():
            line = self.process.stdout.readline()

            if not line:
                break

            if "METHOD" in line:
                for method_name in java_methods:
                    if method_name in line:
                        if not self.methods_por[java_methods[method_name]]:
                            print(
                                f"[+] Method '{java_methods[method_name]}' found in logcat."
                            )

                        self.methods_por[java_methods[method_name]] += 1

    def stop(self):
        self._stop_event.set()

        if self.process:
            self.process.terminate()
            self.process.wait()
