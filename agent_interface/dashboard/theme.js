(()=>{
 const root=document.documentElement;
 try{root.dataset.theme=localStorage.getItem('photon-theme')||'dark'}catch{root.dataset.theme='dark'}
 document.addEventListener('DOMContentLoaded',()=>{
  const button=document.createElement('button');
  button.type='button';button.className='theme-toggle';
  function update(){button.textContent=root.dataset.theme==='light'?'Dark theme':'Light theme';button.setAttribute('aria-label','Switch to '+button.textContent.toLowerCase())}
  button.onclick=()=>{root.dataset.theme=root.dataset.theme==='light'?'dark':'light';try{localStorage.setItem('photon-theme',root.dataset.theme)}catch{}update();window.dispatchEvent(new Event('resize'))};
  (document.querySelector('header')||document.querySelector('nav')).append(button);update();
  document.querySelectorAll('nav a').forEach(a=>{if(new URL(a.href).pathname===location.pathname)a.setAttribute('aria-current','page')});
 });
})();
