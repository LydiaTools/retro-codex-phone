"use strict";
const byId = id => document.getElementById(id);
const token = document.querySelector('meta[name="retro-token"]').content;
let current = {}, seenTranscript = null, recording = false, stopping = false;
let stream, context, source, capture, parts = [], frames = 0, timer;

async function api(path, value={}, audio=false) {
 const r=await fetch('/api/'+path,{method:'POST',headers:{'X-Retro-Token':token,'Content-Type':audio?'audio/wav':'application/json'},body:audio?value:JSON.stringify(value)});
 const result=await r.json(); if(!r.ok)throw new Error(result.error||'Operation failed.'); return result;
}
function error(text=''){byId('error').textContent=text;}
function action(work){return async()=>{try{error();await work();}catch(e){error(e.message);}};}

async function findMicrophones(){
 const consent=await navigator.mediaDevices.getUserMedia({audio:true});consent.getTracks().forEach(t=>t.stop());
 const devices=await navigator.mediaDevices.enumerateDevices();const select=byId('microphone');const old=select.value;
 select.replaceChildren(new Option('System default','default'));
 devices.filter(d=>d.kind==='audioinput'&&d.deviceId!=='default'&&d.deviceId!=='communications').forEach((d,i)=>select.add(new Option(d.label||'Microphone '+(i+1),d.deviceId)));
 if([...select.options].some(o=>o.value===old))select.value=old;
}
function wav(chunks, rate){
 const length=chunks.reduce((n,c)=>n+c.length,0),buffer=new ArrayBuffer(44+length*2),v=new DataView(buffer);
 const text=(offset,s)=>[...s].forEach((c,i)=>v.setUint8(offset+i,c.charCodeAt(0)));
 text(0,'RIFF');v.setUint32(4,36+length*2,true);text(8,'WAVE');text(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);text(36,'data');v.setUint32(40,length*2,true);
 let p=44;chunks.forEach(c=>c.forEach(s=>{v.setInt16(p,Math.max(-1,Math.min(1,s))*32767,true);p+=2;}));return new Blob([buffer],{type:'audio/wav'});
}
async function toggleRecord(){
 if(stopping)return;
 if(recording){
  stopping=true;recording=false;clearTimeout(timer);capture.disconnect();source.disconnect();stream.getTracks().forEach(t=>t.stop());
  const rate=context.sampleRate;await context.close();byId('record').textContent='● Record';byId('record').classList.remove('active');
  try{await api('audio',wav(parts,rate),true);}finally{stopping=false;parts=[];}
  return;
 }
 if(current.busy)throw new Error('Finish the current operation first.');
 if(!current.voice_ready)throw new Error('Click Prepare local voice before recording.');
 const id=byId('microphone').value;
 stream=await navigator.mediaDevices.getUserMedia({audio:id==='default'?true:{deviceId:{exact:id},channelCount:1}});
 try{
  context=new AudioContext({sampleRate:16000});await context.resume();source=context.createMediaStreamSource(stream);
  // A short-lived capture node; released after each recording, never always listening.
  capture=context.createScriptProcessor(4096,1,1);parts=[];frames=0;
  capture.onaudioprocess=e=>{if(recording){const samples=new Float32Array(e.inputBuffer.getChannelData(0));parts.push(samples);frames+=samples.length;}};
  source.connect(capture);capture.connect(context.destination);recording=true;
  byId('record').textContent='■ Stop recording';byId('record').classList.add('active');timer=setTimeout(()=>action(toggleRecord)(),110000);
 }catch(e){stream.getTracks().forEach(t=>t.stop());throw e;}
}
async function send(){
 if(recording)throw new Error('Double tap or click Stop recording, then review the text before sending.');
 if(stopping||current.busy)throw new Error('Wait for the current operation to finish.');
 await api('send',{agent:byId('agent').value,workspace:byId('workspace').value,prompt:byId('prompt').value,allow_edits:byId('allowEdits').checked});
}
function backspace(){
 const input=byId('prompt'),start=input.selectionStart,end=input.selectionEnd;
 const a=start===end?Math.max(0,start-1):start;
 input.value=input.value.slice(0,a)+input.value.slice(end);input.focus();input.setSelectionRange(a,a);
}
async function poll(){
 try{
  const r=await fetch('/api/status',{headers:{'X-Retro-Token':token}});if(!r.ok)throw new Error('Connection lost');current=await r.json();
  byId('status').textContent=recording?'Listening':current.status;
  if(current.transcript!==seenTranscript){byId('prompt').value=current.transcript;seenTranscript=current.transcript;}
  if(current.reply)byId('reply').textContent=current.reply;
  byId('prepare').disabled=current.busy||recording;byId('send').disabled=current.busy||recording;byId('clear').disabled=current.busy||recording;
  byId('agent').disabled=current.busy||recording;byId('workspace').disabled=current.busy||recording;byId('allowEdits').disabled=current.busy||recording;
  byId('record').disabled=current.busy||stopping;
  byId('voiceStatus').textContent=current.voice_ready?'Local voice is ready. Choose your handset microphone.':'First use downloads the Whisper base model. Audio stays on this computer.';
  byId('agentStatus').textContent=current.agents[byId('agent').value]?'CLI found. Use your own signed-in account.':'CLI not found. Install it using the setup guide.';
  byId('buttonStatus').textContent=current.buttons_status;byId('observed').textContent=current.observed_keys.length?'Detected: '+current.observed_keys.map(k=>({play:'⏯',up:'＋',down:'−'}[k])).join('  '):'No buttons detected yet';
  byId('buttons').textContent=current.buttons_on?'Disable':'Enable';
  if(current.error)error(current.error);
  for(const name of current.actions){if(name==='record')await action(toggleRecord)();if(name==='send')await action(send)();if(name==='clear')backspace();}
 }catch(e){byId('status').textContent='Console disconnected';}
 setTimeout(poll,700);
}
byId('refreshDevices').onclick=action(findMicrophones);
byId('prepare').onclick=action(()=>api('prepare'));
byId('record').onclick=action(toggleRecord);byId('send').onclick=action(send);
byId('backspace').onclick=backspace;
byId('clear').onclick=action(async()=>{await api('clear');byId('prompt').value='';byId('reply').textContent='Choose a project folder and send your first prompt.';});
byId('cancel').onclick=action(()=>api('cancel'));
byId('buttons').onclick=action(()=>api('buttons',{enabled:!current.buttons_on,test:byId('testButtons').checked}));
byId('testButtons').onchange=action(()=>api('button-mode',{test:byId('testButtons').checked}));
byId('audioFile').onchange=action(async()=>{const f=byId('audioFile').files[0];if(f)await api('audio',f,true);byId('audioFile').value='';});
byId('speak').onclick=()=>{if(current.reply){speechSynthesis.cancel();const utterance=new SpeechSynthesisUtterance(current.reply.slice(0,12000));speechSynthesis.speak(utterance);}};
addEventListener('pagehide',()=>{if(stream)stream.getTracks().forEach(t=>t.stop());if(context)context.close();});
poll();
