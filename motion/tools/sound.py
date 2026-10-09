import json,sys,wave
import numpy as np
ev=json.load(open(sys.argv[1])); out=sys.argv[2]
SR=44100; dur=ev['dur']; N=int(SR*dur)+SR
t=np.arange(N)/SR
mix=np.zeros(N)
rng=np.random.default_rng(3)
def env(n,a,d):
    e=np.ones(n); A=int(a*SR); e[:A]=np.linspace(0,1,A) if A else 1
    return e*np.exp(-np.arange(n)/SR/d)
def add(x,start,gain=1.0):
    i=int(start*SR); x=x[:max(0,N-i)]; mix[i:i+len(x)]+=x*gain
midi=lambda m:440*2**((m-69)/12)
# ---- musique : 96 BPM, Am F C G, pads + arpège + rythme doux
bpm=96; beat=60/bpm; bar=4*beat
chords=[[57,60,64],[53,57,60],[48,52,55],[55,59,62]]
def saw_pad(f,n):
    tt=np.arange(n)/SR; s=np.zeros(n)
    for k in range(1,8): s+=np.sin(2*np.pi*f*k*tt*(1+0.002*(k%2)))/k
    return s
b=0; pos=0.0
while pos<dur:
    ch=chords[b%4]; n=int(bar*SR)
    pad=sum(saw_pad(midi(m),n) for m in ch)/3
    e=np.minimum(1,np.arange(n)/(0.3*SR))*np.minimum(1,(n-np.arange(n))/(0.3*SR))
    add(pad*e,pos,0.045)
    add(np.sin(2*np.pi*midi(ch[0]-12)*np.arange(n)/SR)*env(n,0.01,1.2),pos,0.10)  # basse
    for k in range(8):  # arpège
        m=ch[k%3]+12+(12 if k in (3,7) else 0); n2=int(beat/2*SR)
        tone=np.sin(2*np.pi*midi(m)*np.arange(n2)/SR)+0.3*np.sin(2*np.pi*midi(m)*2*np.arange(n2)/SR)
        add(tone*env(n2,0.003,0.18),pos+k*beat/2,0.05)
    for k in range(4):  # kick + charleston
        n3=int(0.25*SR); tt=np.arange(n3)/SR
        if k in (0,2): add(np.sin(2*np.pi*(50+90*np.exp(-tt*30))*tt)*np.exp(-tt*12),pos+k*beat,0.22)
        else: add(rng.normal(0,1,n3)*np.exp(-tt*35),pos+k*beat,0.05)
        add(rng.normal(0,1,int(0.05*SR))*np.exp(-np.arange(int(0.05*SR))/SR*90),pos+k*beat+beat/2,0.025)
    b+=1; pos+=bar
# fondu musique fin
fade=np.clip((dur-t)/1.0,0,1); mix*=fade
# ---- effets
def whoosh():
    n=int(0.45*SR); x=rng.normal(0,1,n); y=np.zeros(n); a=0.0
    cut=np.linspace(0.02,0.35,n)**1.5
    for i in range(n): a+= cut[i]*(x[i]-a); y[i]=a
    return y*np.sin(np.linspace(0,np.pi,n))**2*1.6
def pop():
    n=int(0.12*SR); tt=np.arange(n)/SR
    return np.sin(2*np.pi*(500+900*np.exp(-tt*40))*tt)*np.exp(-tt*30)
def tick():
    n=int(0.06*SR); tt=np.arange(n)/SR
    return (np.sin(2*np.pi*2200*tt)+0.5*rng.normal(0,1,n))*np.exp(-tt*120)
def ding():
    n=int(0.9*SR); tt=np.arange(n)/SR
    return (np.sin(2*np.pi*1318*tt)+0.5*np.sin(2*np.pi*1975*tt)+0.25*np.sin(2*np.pi*2637*tt))*np.exp(-tt*4)
FX={'whoosh':(whoosh,0.35),'pop':(pop,0.35),'tick':(tick,0.5),'ding':(ding,0.25)}
cache={}
for e in ev['events']:
    f,gn=FX[e['type']]
    if e['type'] not in cache or e['type']=='whoosh': cache[e['type']]=f()
    add(cache[e['type']],e['t'],gn)
mix=mix[:int(SR*dur)]
mix=mix/max(1e-6,np.abs(mix).max())*0.89
st=np.stack([mix,mix],1)
w=wave.open(out,'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((st*32767).astype('<i2').tobytes()); w.close()
print('ok',dur)
