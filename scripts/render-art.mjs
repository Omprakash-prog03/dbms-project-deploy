// Rebuild the small, locally rendered glass sculptures used by the interface.
// npm install && npm run art
import http from "node:http";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium as playwright } from "playwright-core";
import chromium, { inflate, setupLambdaEnvironment } from "@sparticuz/chromium";
// The bundled libraries also support minimal Linux CI/sandbox environments.
await inflate(
  path.resolve("node_modules/@sparticuz/chromium/bin/al2023.tar.br"),
);
setupLambdaEnvironment("/tmp/al2023/lib");

const root = path.resolve(".");
const html = `<!doctype html><html><head><style>*{margin:0}html,body{width:512px;height:512px;background:transparent}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"/node_modules/three/build/three.module.js","three/addons/":"/node_modules/three/examples/jsm/"}}</script></head><body><script type="module">
import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
const renderer = new THREE.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});
renderer.setSize(512,512); renderer.setPixelRatio(1.5);
renderer.setClearColor(0x000000,0); renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=.9;
document.body.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(),0.04).texture;
const camera = new THREE.PerspectiveCamera(36,1,.1,100); camera.position.set(0,0,7.7);
const material = new THREE.MeshPhysicalMaterial({color:0xe9f5ff,metalness:.04,roughness:.08,transmission:.95,thickness:.9,ior:1.35,clearcoat:1,clearcoatRoughness:.07,envMapIntensity:1.0,transparent:true,opacity:.94});
const group = new THREE.Group(); scene.add(group);
const add = (geo) => {const m=new THREE.Mesh(geo,material);group.add(m);return m;};
class Flower extends THREE.Curve {getPoint(t,target=new THREE.Vector3()){t*=Math.PI*2;const r=.94+.5*Math.cos(5*t);return target.set(r*Math.cos(t),r*Math.sin(t),.38*Math.sin(3*t));}}
class Helix extends THREE.Curve {getPoint(t,target=new THREE.Vector3()){const a=t*Math.PI*5;return target.set(.87*Math.cos(a), (t-.5)*2.7,.87*Math.sin(a));}}
const shape = new URLSearchParams(location.search).get('shape');
if(shape==='flower'){add(new THREE.TubeGeometry(new Flower(),320,.15,24,true));group.rotation.set(.3,-.32,.3);}
else if(shape==='knot'){add(new THREE.TorusKnotGeometry(.91,.22,240,40,2,3));group.rotation.set(.2,.35,-.4);}
else if(shape==='orbit'){for(let i=0;i<3;i++){const m=add(new THREE.TorusGeometry(1.13,.16,36,150));m.rotation.set(.5+i*.7,i*.85,.3);}group.rotation.z=-.35;}
else if(shape==='bloom'){add(new THREE.SphereGeometry(.9,64,48));const vertices=new THREE.IcosahedronGeometry(1,0).getAttribute('position');const seen=new Set();for(let i=0;i<vertices.count;i++){const v=new THREE.Vector3().fromBufferAttribute(vertices,i).normalize();const key=v.toArray().map(x=>x.toFixed(2)).join();if(seen.has(key))continue;seen.add(key);const m=add(new THREE.SphereGeometry(.34,32,24));m.position.copy(v.multiplyScalar(1.02));}group.rotation.set(.5,.2,.4);}
else if(shape==='ribbon'){add(new THREE.TorusKnotGeometry(.85,.16,320,32,3,4));group.rotation.set(.5,-.3,.4);}
else {add(new THREE.TubeGeometry(new Helix(),240,.21,32,false));group.rotation.set(.3,0,-.4);}
const light = new THREE.DirectionalLight(0xffffff,.7);light.position.set(-3,4,5);scene.add(light);
scene.add(new THREE.AmbientLight(0xc8dcff,.15));
renderer.render(scene,camera);window.ready=true;
</script></body></html>`;
const server = http.createServer(async (req, res) => {
  try {
    if (req.url.startsWith("/?") || req.url === "/") {
      res.setHeader("Content-Type", "text/html");
      return res.end(html);
    }
    const filename = path.resolve(
      root,
      "." + decodeURIComponent(req.url.split("?")[0]),
    );
    if (!filename.startsWith(root + "/node_modules/three/")) {
      res.writeHead(404);
      return res.end();
    }
    res.setHeader("Content-Type", "application/javascript");
    res.end(await fs.readFile(filename));
  } catch {
    res.writeHead(404);
    res.end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await playwright.launch({
    executablePath: await chromium.executablePath(),
    args: chromium.args,
    headless: true,
  });
  const page = await browser.newPage({
    viewport: { width: 512, height: 512 },
    deviceScaleFactor: 1,
  });
  page.on("pageerror", (err) => console.error(err));
  await fs.mkdir("static/images", { recursive: true });
  for (const shape of ["flower", "knot", "orbit", "bloom", "ribbon", "helix"]) {
    await page.goto(
      "http://127.0.0.1:" + server.address().port + "/?shape=" + shape,
    );
    await page.waitForFunction(() => window.ready);
    await page.screenshot({
      path: "static/images/" + shape + ".png",
      omitBackground: true,
    });
    console.log("Rendered " + shape);
  }
} finally {
  await browser?.close();
  server.close();
}
