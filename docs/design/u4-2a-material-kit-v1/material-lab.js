const scale = document.querySelector('#scale');
const seams = document.querySelector('#seams');
scale.addEventListener('change', () => {
  document.documentElement.style.setProperty('--texture-size', `${scale.value}px`);
});
seams.addEventListener('change', () => {
  document.body.classList.toggle('show-seams', seams.checked);
});
