// Pre-script: records the analysis options the project is built with, so that one exe gives the
// same functions on every machine. Every option is set explicitly, and a name Ghidra does not
// know fails the run instead of being skipped. With the argument `list` it only prints every
// option and its value.
//
// Built for Ghidra 12.x, language x86:LE:32:default, compiler spec windows (setup.sh passes both
// on import).
//
// @category benilla

import ghidra.app.plugin.core.analysis.AutoAnalysisManager;
import ghidra.app.script.GhidraScript;
import ghidra.framework.options.Options;
import ghidra.program.model.listing.Program;

import java.util.LinkedHashMap;
import java.util.Map;

public class SetOptions extends GhidraScript {

    // Analyzer name -> enabled. Everything not listed keeps Ghidra's default, which the run
    // prints in full so that it is on record too.
    private static final Map<String, String> OPTIONS = new LinkedHashMap<>();
    static {
        // What finds functions and code. Aggressive finding is off: it turns data into code.
        OPTIONS.put("Disassemble Entry Points", "true");
        OPTIONS.put("Function Start Search", "true");
        OPTIONS.put("Subroutine References", "true");
        OPTIONS.put("Non-Returning Functions - Discovered", "true");
        OPTIONS.put("Shared Return Calls", "true");
        OPTIONS.put("Aggressive Instruction Finder", "false");
        OPTIONS.put("Create Address Tables", "true");
        OPTIONS.put("Condense Filler Bytes", "false");
        // References, stack and calling conventions.
        OPTIONS.put("Reference", "true");
        OPTIONS.put("Data Reference", "true");
        OPTIONS.put("Stack", "true");
        OPTIONS.put("Scalar Operand References", "true");
        OPTIONS.put("x86 Constant Reference Analyzer", "true");
        OPTIONS.put("Call Convention ID", "true");
        OPTIONS.put("Windows x86 PE Exception Handling", "true");
        OPTIONS.put("Windows x86 PE RTTI Analyzer", "true");
        OPTIONS.put("Demangler Microsoft", "true");
        OPTIONS.put("Function ID", "true");
        // Off: slow, or they add guesses to a table that records only what the bytes show.
        OPTIONS.put("Decompiler Parameter ID", "false");
        OPTIONS.put("Decompiler Switch Analysis", "false");
        OPTIONS.put("ASCII Strings", "true");
        OPTIONS.put("Embedded Media", "false");
        OPTIONS.put("PDB Universal", "false");
        OPTIONS.put("Apply Data Archives", "true");
    }

    @Override
    public void run() throws Exception {
        String version = currentProgram.getLanguageID() + " / " + currentProgram.getCompilerSpec().getCompilerSpecID();
        println("SetOptions: Ghidra " + getGhidraVersion() + ", " + version);
        if (!getGhidraVersion().startsWith("12.")) {
            throw new IllegalStateException("built for Ghidra 12.x, this is " + getGhidraVersion());
        }
        if (!"x86:LE:32:default".equals(currentProgram.getLanguageID().getIdAsString())) {
            throw new IllegalStateException("wrong language " + currentProgram.getLanguageID());
        }
        // Registers every analyzer's options.
        AutoAnalysisManager.getAnalysisManager(currentProgram);
        Options opts = currentProgram.getOptions(Program.ANALYSIS_PROPERTIES);

        String[] args = getScriptArgs();
        if (args.length > 0 && args[0].equals("list")) {
            for (String n : opts.getOptionNames()) {
                println("option: " + n + " = " + opts.getValueAsString(n));
            }
            return;
        }
        for (Map.Entry<String, String> e : OPTIONS.entrySet()) {
            if (!opts.contains(e.getKey())) {
                throw new IllegalStateException("unknown analysis option: " + e.getKey());
            }
            setAnalysisOption(currentProgram, e.getKey(), e.getValue());
        }
        for (String n : opts.getOptionNames()) {
            println("option: " + n + " = " + opts.getValueAsString(n));
        }
    }
}
