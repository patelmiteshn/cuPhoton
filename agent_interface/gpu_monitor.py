"""Read-only, cached GB10 telemetry; unavailable values remain null."""
import xml.etree.ElementTree as ET
import csv
import io
import subprocess
import threading
import time
from pathlib import Path
LOCK=threading.Lock()
CACHE={}

def number(value):
    try: return float(value.strip())
    except ValueError: return None

def snapshot():
    global CACHE
    with LOCK:
        if CACHE and time.time()-CACHE['timestamp']<1.5: return CACHE
        try:
            result=subprocess.run(['nvidia-smi','--query-gpu=name,utilization.gpu,utilization.memory,temperature.gpu,power.draw,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True)
            rows=list(csv.reader(io.StringIO(result.stdout)))
            gpus=[dict(zip(['name','utilization','memory_utilization','temperature','power','memory_used_mib','memory_total_mib'],[r[0].strip()]+[number(v) for v in r[1:]])) for r in rows]
            mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
            processes=[]
            compute_memory=None
            try:
                result=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,check=True)
                for row in csv.reader(io.StringIO(result.stdout)):
                    if len(row)==3:
                        processes.append({'pid':row[0].strip(),'name':row[1].strip(),'memory_mib':number(row[2])})
                if all(p['memory_mib'] is not None for p in processes):
                    compute_memory=sum(p['memory_mib'] for p in processes)/1024
            except (OSError,subprocess.SubprocessError,ValueError):
                pass
            gpu_processes=None
            try:
                result=subprocess.run(['nvidia-smi','-q','-x'],capture_output=True,text=True,timeout=5,check=True)
                gpu_processes=[]
                for gpu in ET.fromstring(result.stdout).findall('gpu'):
                    for proc in gpu.findall('./processes/process_info'):
                        memory=proc.findtext('used_memory','N/A').replace('MiB','').strip()
                        gpu_processes.append({'pid':proc.findtext('pid',''), 'name':proc.findtext('process_name','Unknown'), 'type':proc.findtext('type','Unknown'), 'memory_mib':number(memory), 'gpu':gpu.get('id','')})
                gpu_processes.sort(key=lambda p:p['memory_mib'] if p['memory_mib'] is not None else -1,reverse=True)
            except (OSError,subprocess.SubprocessError,ValueError,ET.ParseError):
                pass
            CACHE={'gpu_processes':gpu_processes,'compute_processes':processes,'compute_memory_used_gib':compute_memory,'timestamp':time.time(),'gpus':gpus,'system_ram_used_gib':(mem['MemTotal']-mem['MemAvailable'])/1048576,'system_ram_total_gib':mem['MemTotal']/1048576}
        except (OSError,subprocess.SubprocessError,ValueError) as exc:
            CACHE={'timestamp':time.time(),'error':'GPU telemetry unavailable: '+str(exc),'gpus':[]}
        return CACHE
