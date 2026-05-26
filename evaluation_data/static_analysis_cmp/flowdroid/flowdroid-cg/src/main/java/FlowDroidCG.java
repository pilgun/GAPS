import org.xmlpull.v1.XmlPullParserException;
import soot.Scene;
import soot.SootMethod;
import soot.jimple.infoflow.android.InfoflowAndroidConfiguration;
import soot.jimple.infoflow.android.SetupApplication;
import soot.jimple.toolkits.callgraph.Edge;
import soot.jimple.infoflow.InfoflowConfiguration;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Iterator;

import static java.lang.System.exit;

public class FlowDroidCG {
    public static void main(String[] args) throws IOException, XmlPullParserException {
        if (args.length < 3) {
            System.err.println("Usage: java FlowDroidCG <platforms_dir> <apk_path> <output_dir>");
            exit(1);
        }

        String platforms_dir = args[0];
        String apk_path = args[1];
        String output_dir = args[2];

        // Ensure the output directory exists
        Path outputDirPath = Paths.get(output_dir);
        if (!Files.exists(outputDirPath)) {
            Files.createDirectories(outputDirPath);
        }

        InfoflowAndroidConfiguration config = new InfoflowAndroidConfiguration();
        config.getAnalysisFileConfig().setAndroidPlatformDir(new java.io.File(platforms_dir));
        config.getAnalysisFileConfig().setTargetAPKFile(new java.io.File(apk_path));
        
	config.getCallbackConfig().setEnableCallbacks(true);
	config.setCodeEliminationMode(InfoflowConfiguration.CodeEliminationMode.NoCodeElimination);
	config.getPathConfiguration().setPathReconstructionMode(InfoflowConfiguration.PathReconstructionMode.Precise);	
	        // Set the call graph algorithm to CHA
        config.setCallgraphAlgorithm(InfoflowAndroidConfiguration.CallgraphAlgorithm.CHA);
        SetupApplication analyzer = new SetupApplication(config);
	analyzer.getConfig().setEnableReflection(true);
        analyzer.constructCallgraph();

        // Write the callgraph to a JSON file
        String outputFilePath = output_dir + "/callgraph.json";
        try (FileWriter writer = new FileWriter(outputFilePath)) {
            writer.write("{ \"edges\" : [\n");
            for (Iterator<Edge> edgeIt = Scene.v().getCallGraph().iterator(); edgeIt.hasNext(); ) {
                Edge edge = edgeIt.next();
                SootMethod smSrc = edge.src();
                SootMethod smDest = edge.tgt();
		if(smSrc != null && smDest != null){
			writer.write(
				"    { \"src\": \"" + smSrc.getBytecodeSignature() + "\", " +
				      "\"dst\": \"" + smDest.getBytecodeSignature() + "\" }");
		}
		if (edgeIt.hasNext())
                    writer.write(",\n");
                else
                    writer.write("\n");
            }
            writer.write("  ]\n}");
        }

        System.out.println("Callgraph saved to: " + outputFilePath);
    }
}
