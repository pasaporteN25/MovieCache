import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const context = vm.createContext({ URL });
const modules = new Map();
async function moduleAt(url) {
  if (!modules.has(url.href)) modules.set(url.href, readFile(url, 'utf8').then(source =>
    new vm.SourceTextModule(source, { context, identifier: url.href })));
  return modules.get(url.href);
}
const module = await moduleAt(new URL('../../src/movie_inbox/web/static/js/core/back-cover-images.js', import.meta.url));
await module.link((specifier, parent) => moduleAt(new URL(specifier, parent.identifier)));
await module.evaluate();
const { backCoverImages: images, backCoverImageKey: key, renderBackCoverImages: render } = module.namespace;

test('zero, one and two images retain honest roles and a stable order', () => {
  assert.equal(images({}).length, 0);
  assert.equal(images({ page_image: 'https://example.org/poster.jpg' })[0].role, 'poster');
  const pair = images({ page_image: 'https://example.org/poster.jpg', backdrop_image: 'https://example.org/scene.jpg' });
  assert.equal(pair.map(image => image.role).join(','), 'backdrop,poster');
});

test('malformed or credential-bearing URLs never become image requests', () => {
  for (const value of ['javascript:alert(1)', 'data:image/png;base64,a', '/relative.jpg', 'not a URL', 'https://user:secret@example.org/a.jpg']) {
    assert.equal(images({page_image: value}).length, 0, value);
  }
});

test('known size variants are one asset, with poster role when shared', () => {
  const pairs = [
    ['https://image.tmdb.org/t/p/w500/one.jpg', 'https://image.tmdb.org/t/p/original/one.jpg'],
    ['https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/One.jpg/300px-One.jpg', 'https://upload.wikimedia.org/wikipedia/commons/a/ab/One.jpg'],
    ['https://m.media-amazon.com/images/M/one._V1_SX300.jpg', 'https://ia.media-imdb.com/images/M/one._V1_SX500.jpg'],
    ['https://pics.filmaffinity.com/one-123-large.jpg', 'https://images.filmaffinity.com/one-123-mmed.jpg'],
    ['https://cdn.myanimelist.net/images/anime/12/34l.jpg', 'https://cdn.myanimelist.net/images/anime/12/34.jpg'],
    ['https://example.org/a.jpg#first', 'https://example.org/a.jpg#second'],
  ];
  for (const [poster, backdrop] of pairs) {
    assert.equal(key(poster), key(backdrop));
    const result = images({page_image: poster, backdrop_image: backdrop});
    assert.equal(result.length, 1);
    assert.equal(result[0].role, 'poster');
  }
});

test('different images and unknown query identifiers are not collapsed', () => {
  for (const [a, b] of [
    ['https://image.tmdb.org/t/p/w500/one.jpg', 'https://image.tmdb.org/t/p/w500/two.jpg'],
    ['https://example.org/image?id=1', 'https://example.org/image?id=2'],
  ]) assert.equal(images({page_image: a, backdrop_image: b}).length, 2);
});

test('markup uses the existing proxy, escapes data and never invents a film still', () => {
  const html = render({page_image: 'https://example.org/a.jpg?name="x"'}, '<Obra>');
  assert.match(html, /data-image-count="1"/);
  assert.match(html, /src="\/image-cache\?url=https%3A/);
  assert.match(html, /Portada de &lt;Obra&gt;/);
  assert.doesNotMatch(html, /Fotograma|src="https:/);
  const empty = render({}, 'Obra');
  assert.match(empty, /Sin imágenes guardadas/);
  assert.doesNotMatch(empty, /<img|<figure/);
});
