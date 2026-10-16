(async()=>{
  const SR=32000, SEC=40, OFF=new OfflineAudioContext(2,SR*SEC,SR);
  const sv={AC,master,reverb,out:BGM.out,bus:BGM.bus,rev:BGM.rev};
  AC=OFF; master=OFF.createGain(); master.connect(OFF.destination);
  BGM.out=OFF.createGain(); BGM.out.gain.value=musicVol*2; BGM.out.connect(OFF.destination);
  BGM.bus=OFF.createGain(); BGM.bus.gain.value=.29; BGM.bus.connect(BGM.out);
  { const len=SR*1.6, ir=OFF.createBuffer(2,len,SR); for(let c=0;c<2;c++){ const ch=ir.getChannelData(c); for(let i=0;i<len;i++) ch[i]=(Math.random()*2-1)*Math.pow(1-i/len,2.5); }
    const cv=OFF.createConvolver(), lp=OFF.createBiquadFilter(), wg=OFF.createGain(); cv.buffer=ir; lp.type='lowpass'; lp.frequency.value=1800; wg.gain.value=.3;
    BGM.rev=OFF.createGain(); BGM.rev.connect(cv); cv.connect(lp); lp.connect(wg); wg.connect(BGM.out); }
  for(const ev of MIDI_EV){ if(ev.t>SEC-1) break; playMidi(ev.tr,ev.e,ev.t); }
  const buf=await OFF.startRendering();
  AC=sv.AC; master=sv.master; reverb=sv.reverb; BGM.out=sv.out; BGM.bus=sv.bus; BGM.rev=sv.rev;
  const a=new Float32Array(buf.length); const l=buf.getChannelData(0), r=buf.getChannelData(1); for(let i=0;i<a.length;i++) a[i]=(l[i]+r[i])/2;
  let ss=0,pk=0; for(const x of a){ ss+=x*x; if(Math.abs(x)>pk) pk=Math.abs(x); }
  const rms=Math.sqrt(ss/a.length);
  const N=8192, spec=new Float64Array(N/2+1);
  const fft=(re,im)=>{ const n=re.length; for(let i=1,j=0;i<n;i++){ let bit=n>>1; for(;j&bit;bit>>=1) j^=bit; j^=bit; if(i<j){ [re[i],re[j]]=[re[j],re[i]]; [im[i],im[j]]=[im[j],im[i]]; } }
    for(let len=2;len<=n;len<<=1){ const ang=-2*Math.PI/len, wr=Math.cos(ang), wi=Math.sin(ang); for(let i=0;i<n;i+=len){ let cr=1,ci=0; for(let j=0;j<len/2;j++){ const ur=re[i+j], ui=im[i+j], vr=re[i+j+len/2]*cr-im[i+j+len/2]*ci, vi=re[i+j+len/2]*ci+im[i+j+len/2]*cr; re[i+j]=ur+vr; im[i+j]=ui+vi; re[i+j+len/2]=ur-vr; im[i+j+len/2]=ui-vi; const t=cr*wr-ci*wi; ci=cr*wi+ci*wr; cr=t; } } } };
  for(let s=0;s+N<a.length;s+=N){ const re=new Float64Array(N), im=new Float64Array(N); for(let i=0;i<N;i++) re[i]=a[s+i]*(.5-.5*Math.cos(2*Math.PI*i/N)); fft(re,im); for(let k=0;k<=N/2;k++) spec[k]+=re[k]*re[k]+im[k]*im[k]; }
  let tot=0; for(const v of spec) tot+=v;
  const bands=[[30,120],[120,300],[300,1000],[1000,3000],[3000,6000],[6000,12000],[12000,16000]].map(([lo,hi])=>{ let e=0; for(let k=0;k<=N/2;k++){ const f=k*SR/N; if(f>=lo&&f<hi) e+=spec[k]; } return lo+'-'+hi+':'+(100*e/tot).toFixed(1)+'%'; });
  return 'rms='+(20*Math.log10(rms)).toFixed(1)+'dB peak='+pk.toFixed(2)+' | '+bands.join(' ');
})()
