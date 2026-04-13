import time, threading
path='scratch/test.log'
open(path,'w').close()
f=open(path,'r',encoding='utf-8')
print('t:', repr(f.read()))
def w():
 time.sleep(1)
 open(path,'a',encoding='utf-8').write('hello\n')
 print('wrote!')
threading.Thread(target=w).start()
time.sleep(2)
print('r1:', repr(f.read()))
f.seek(0, 1)
print('r2:', repr(f.read()))
f.seek(f.tell())
print('r3:', repr(f.read()))
