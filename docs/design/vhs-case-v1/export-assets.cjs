// Mechanical size exports from approved Imagegen originals; no artistic edits.
const fs = require('node:fs');
const path = require('node:path');
const sharp = require(process.env.SHARP_MODULE || 'sharp');
const destination = path.resolve('src/movie_inbox/web/static/img/brand');
async function main() {
  fs.mkdirSync(destination, {recursive:true});
  for (const name of ['movie-inbox-sticker', 'movie-inbox-logo']) {
    const source = path.join(destination, `${name}-master.png`);
    for (const width of [128, 256, 512, 1024]) {
      await sharp(source).resize({width}).png().toFile(path.join(destination, `${name}-${width}.png`));
      await sharp(source).resize({width}).webp({quality:90}).toFile(path.join(destination, `${name}-${width}.webp`));
    }
  }
  await sharp(path.join(destination,'vhs-blank-master.png')).resize({width:512}).webp({quality:88}).toFile(path.join(destination,'vhs-blank-512.webp'));
}
main().catch(error => { console.error(error); process.exitCode=1; });
