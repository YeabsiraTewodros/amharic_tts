 // Interactive background: move gradient with pointer/touch and toggle theme on tap
    (function(){
      const root = document.documentElement;
      let tapped = false;
      function setPos(x,y){
        root.style.setProperty('--bg-x', x + '%');
        root.style.setProperty('--bg-y', y + '%');
      }
      function onPointer(e){
        const cx = (e.clientX !== undefined) ? e.clientX : (e.touches && e.touches[0] && e.touches[0].clientX) || 0;
        const cy = (e.clientY !== undefined) ? e.clientY : (e.touches && e.touches[0] && e.touches[0].clientY) || 0;
        const px = Math.round((cx / window.innerWidth) * 100);
        const py = Math.round((cy / window.innerHeight) * 100);
        setPos(px, py);
      }
      window.addEventListener('pointermove', onPointer, {passive:true});
      window.addEventListener('touchmove', onPointer, {passive:true});
      // header theme toggle removed; theme choice remains available in Settings modal
    })();