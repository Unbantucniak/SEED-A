const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const Module = require("node:module");

async function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "seeda-empty-search-"));
  const source = path.join(root, "target.py"), value = "def f(): return 1";
  fs.writeFileSync(source, value);
  const uri = {fsPath:source,scheme:"file",toString:()=>source};
  const folder = {name:"fixture",uri:{fsPath:root,toString:()=>root}};
  const commands = new Map();
  let allowBrowse = false, allowSelection = false, browseCalls = 0, diffs = 0;
  let optionsShown = [];
  const answer = "浏览本项目此版本的已验证经验";
  const vscode = {
    workspace: {isTrusted:true,textDocuments:[],getWorkspaceFolder:()=>folder,
      registerTextDocumentContentProvider:()=>({dispose(){}}),
      getConfiguration:()=>({get:(k,d)=>({memoryScope:"repo",memoryVersion:"v1"}[k]??d)})},
    window:{activeTextEditor:{document:{fileName:source,uri,isDirty:false,languageId:"python",version:1,eol:1,
      getText:()=>value,offsetAt:()=>0},selection:{isEmpty:false,start:{}}},
      showInputBox:async()=>"unrelated tectonic plates",showInformationMessage:async(msg, action)=>action===answer&&allowBrowse?answer:undefined,
      showQuickPick:async(rows)=>{optionsShown=rows;return allowSelection?rows[0]:undefined;},showErrorMessage:async()=>undefined},
    EndOfLine:{CRLF:2},Uri:{from:({path})=>({toString:()=>path})},
    commands:{registerCommand:(id,fn)=>{commands.set(id,fn);return {dispose(){}};},
      executeCommand:async(id,...args)=>{if(id==="vscode.diff"){diffs++;return;}return commands.get(id)(...args);}}
  };
  const old=Module._load;
  Module._load=function(name,...args){return name==="vscode"?vscode:old.call(this,name,...args);};
  try {
    const row={id:"valid",requirement:"normalize whitespace",scope:"repo",version:"v1",validated:true,archived:false,
      source_path:"text.py",test_path:"test_text.py",code:"def f(): return 2",receipt:{is_success:true}};
    const api={search:async()=>[],experiences:async(verified)=>{assert.equal(verified,true);browseCalls++;
      return [row,{...row,id:"foreign",scope:"other"},{...row,id:"obsolete",archived:true},{...row,id:"invalid",receipt:{is_success:false}}];}};
    const {registerProjectWorkflow}=require("../out/projectWorkflow");
    registerProjectWorkflow({subscriptions:[],workspaceState:{get:(_,d)=>d}},()=>api,{appendLine(){}});
    const apply=commands.get("seeda.applyExperience");
    assert.equal((await apply()).status,"empty");assert.equal(browseCalls,0);assert.equal(diffs,0);
    allowBrowse=true;
    await apply();assert.equal(browseCalls,1);assert.deepEqual(optionsShown.map(x=>x.row.id),["valid"]);assert.equal(diffs,0);
    allowSelection=true;assert.ok((await apply()).preview);assert.equal(diffs,1);
    assert.equal((await apply({experienceId:"foreign"})).status,"empty");assert.equal(diffs,1);
    const candidates=await commands.get("seeda.browseProjectExperiences")({returnCandidates:true});
    assert.deepEqual(candidates,[{id:"valid",title:row.requirement,source:"text.py",test:"test_text.py"}]);
    assert.equal(fs.readFileSync(source,"utf8"),value);
    console.log("PASS: empty search respects cancel, opt-in manual selection, verified scoped list, same diff and wrong ID");
  } finally {Module._load=old;fs.unlinkSync(source);fs.rmdirSync(root);}
}
main().catch(error=>{console.error(error);process.exitCode=1;});

