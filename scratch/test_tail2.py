import time, subprocess, os
path='scratch/test.log'
open(path,'w').close()
f=open(path,'r',encoding='utf-8')
print('init:', repr(f.read()))

def writer():
    import time
    time.sleep(1)
    with open('scratch/test.log', 'a') as out:
        out.write('from_process\n')

import threading
threading.Thread(target=writer).start()
time.sleep(3)
print('r1 (no seek):', repr(f.read()))
f.seek(f.tell())
print('r2 (after seek):', repr(f.read()))
