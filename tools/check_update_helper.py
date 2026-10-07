"""Windows-only isolated replacement checks; run with the project Python. No real app is modified."""
import hashlib,json,subprocess,tempfile,time,shutil
from pathlib import Path
ps=Path('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
with tempfile.TemporaryDirectory(prefix="driveflow update's ", ignore_cleanup_errors=True) as folder:
    root=Path(folder)
    code=r'''using System; using System.IO; using System.Reflection;
class Probe { public static void Main(string[] args) {
 if(args.Length==2 && args[0]=="--smoke-test") {
 bool good = !Assembly.GetExecutingAssembly().Location.Contains("reject");
 File.WriteAllText(args[1], "{\"ok\":"+(good?"true":"false")+",\"version\":\"1.3.0\",\"monitoring_dependencies\":true}");
 } else File.WriteAllText(Assembly.GetExecutingAssembly().Location+".launched", "ok");
} }'''
    cs=root/'probe.cs';cs.write_text(code)
    compiler=root/'compile.ps1'
    compiler.write_text("param($Source,$Output)\nAdd-Type -Path $Source -OutputAssembly $Output -OutputType ConsoleApplication",encoding='utf-8')
    binary=root/'probe.exe'
    subprocess.run([str(ps),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(compiler),str(cs),str(binary)],check=True,capture_output=True)
    for case in ('success','reject','checksum'):
        area=root/case;area.mkdir()
        target=area/'installed.exe'; target.write_bytes(binary.read_bytes()+b'previous-version')
        before=target.read_bytes()
        source=area/'new.exe';shutil.copyfile(binary,source)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        job=area/'install.json';job.write_text(json.dumps(dict(target=str(target),source=str(source),sha256=digest if case!='checksum' else '0'*64,version='1.3.0',pid=2147483647)),encoding='utf-8')
        result=subprocess.run([str(ps),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path('driveflow/update_helper.ps1').resolve()),'-JobFile',str(job)],capture_output=True,timeout=90)
        log=(area/'result.txt').read_text(encoding='utf-8-sig') if (area/'result.txt').exists() else result.stderr.decode(errors='replace')
        if case=='success':
            assert target.read_bytes()==source.read_bytes(),log
            assert Path(str(target)+'.update-backup').read_bytes()==before,log
        else: assert target.read_bytes()==before,log
        for _ in range(30):
            if Path(str(target)+'.launched').exists(): break
            time.sleep(.1)
        assert Path(str(target)+'.launched').exists(),log
        time.sleep(.2)
        print(case+': OK')
