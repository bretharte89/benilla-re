// Post-script (after analysis): creates every function of symbols/functions.tsv that analysis did
// not make, at its address. Prints one line per row that could not be made a function, and checks
// each function's size against the row's. Argument: the symbols directory.
//
// @category benilla

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;

import java.io.BufferedReader;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

public class CreateFunctions extends GhidraScript {

    @Override
    public void run() throws Exception {
        String dir = getScriptArgs()[0];
        List<String[]> rows = new ArrayList<>();
        try (BufferedReader r = Files.newBufferedReader(Paths.get(dir, "functions.tsv"))) {
            r.readLine();
            String line;
            while ((line = r.readLine()) != null) {
                rows.add(line.split("\t", -1));
            }
        }
        println("CreateFunctions: functions after analysis: "
                + currentProgram.getFunctionManager().getFunctionCount());
        int total = rows.size(), found = 0, created = 0, failed = 0, sizeDiffers = 0;
        for (String[] c : rows) {
            Address a = toAddr(Long.parseLong(c[0].substring(2), 16));
            long size = Long.parseLong(c[1]);
            Function f = getFunctionAt(a);
            if (f != null) {
                found++;
            } else {
                Function inside = getFunctionContaining(a);
                if (inside != null) {
                    println("CreateFunctions: FAIL " + c[0] + " " + c[2] + ": inside " + inside.getName()
                            + " at " + inside.getEntryPoint());
                    failed++;
                    continue;
                }
                if (getInstructionAt(a) == null) {
                    // Data or nothing in the way: clear it, then disassemble.
                    if (getDataAt(a) != null) {
                        clearListing(a);
                    }
                    disassemble(a);
                }
                f = createFunction(a, null);
                if (f == null) {
                    println("CreateFunctions: FAIL " + c[0] + " " + c[2] + ": createFunction returned null");
                    failed++;
                    continue;
                }
                created++;
            }
            // The size of the row runs to the end of the last instruction.
            long end = f.getBody().getMaxAddress().getOffset() - f.getEntryPoint().getOffset() + 1;
            if (f.getBody().getNumAddressRanges() > 1 || end != size) {
                println("CreateFunctions: size " + c[0] + " " + c[2] + ": row " + size + ", ghidra "
                        + f.getBody().getNumAddresses() + " in " + f.getBody().getNumAddressRanges() + " range(s)");
                sizeDiffers++;
            }
        }
        println("CreateFunctions: rows=" + total + " already_functions=" + found + " created=" + created
                + " failed=" + failed + " size_differs=" + sizeDiffers);
        println("CreateFunctions: functions in the program now: "
                + currentProgram.getFunctionManager().getFunctionCount());
    }
}
