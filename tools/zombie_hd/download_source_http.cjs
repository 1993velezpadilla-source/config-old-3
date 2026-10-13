/* CI-only, transient fetch of a *free* author's original itch ZIP.
   Signed CDN URL and raw asset are not printed, committed, or uploaded. */
const { downloadGameDirect } = require("itchio-downloader");
const fs = require("fs");
const path = require("path");

(async () => {
  const dir = process.env.XZIEL_DOWNLOAD_DIR || "/tmp/xziel-hotstrike";
  fs.mkdirSync(dir, { recursive: true });
  const result = await downloadGameDirect({
    itchGameUrl: "https://hotstrikestudio.itch.io/free-stylized-dark-fantasy-zombie",
    downloadDirectory: dir
  });
  const all = [];
  const descend = d => {
    for(const entry of fs.readdirSync(d, {withFileTypes:true})) {
      const p = path.join(d, entry.name);
      if(entry.isDirectory()) descend(p);
      else if(entry.name.toLowerCase().endsWith(".zip")) all.push(p);
    }
  };
  descend(dir);
  if(!all.length) throw new Error("itch.io zero-payment download did not yield a ZIP; manual source needed");
  if(all.length > 1) throw new Error("More than one archive downloaded; not selecting ambiguous source");
  fs.copyFileSync(all[0], "/tmp/SZombie.zip");
  console.log("AUTHOR_ZIP_ACQUIRED_TRANSIENT_PATH=/tmp/SZombie.zip");
  console.log("ARCHIVE_BYTES="+fs.statSync("/tmp/SZombie.zip").size);
})().catch(err => {console.error("ITCH_DIRECT_DOWNLOAD_NOT_AVAILABLE:", err.message); process.exitCode=1});
