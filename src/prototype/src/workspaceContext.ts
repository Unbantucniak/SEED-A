import * as vscode from "vscode";
import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";
function currentBranch(folder: string): string {
    try {
        let git = path.join(folder, ".git");
        if (fs.statSync(git).isFile()) {
            const link = fs.readFileSync(git, "utf8").trim();
            if (!link.startsWith("gitdir: "))
                return "v1";
            git = path.resolve(folder, link.slice(8));
        }
        const head = fs.readFileSync(path.join(git, "HEAD"), "utf8").trim();
        return head.startsWith("ref: refs/heads/") ? head.slice(16) : head.slice(0, 12);
    }
    catch {
        return "v1";
    }
}
export function memoryContext(uri?: vscode.Uri) {
    const folder = uri && vscode.workspace.getWorkspaceFolder?.(uri);
    const config = vscode.workspace.getConfiguration("seeda", uri);
    const name = folder?.name.replace(/[^\p{L}\p{N}._-]+/gu, "-").slice(0, 40) || "project";
    const root = folder?.uri.fsPath;
    const pathKey = root && (process.platform === "win32" ? root.toLowerCase() : root);
    const hash = (text: string) => createHash("sha256").update(text).digest("hex").slice(0, 12);
    const branch = root ? currentBranch(root) : "v1";
    const detected = branch.length <= 40 ? branch : branch.slice(0, 25) + "-" + hash(branch);
    return {
        folder,
        scope: config.get<string>("memoryScope", "").trim() || (pathKey ? name + "-" + hash(pathKey) : "workbench-python"),
        version: config.get<string>("memoryVersion", "").trim() || detected,
    };
}
