# Sanctum reference photos

This directory is the authoritative input surface for photo-driven reconstruction of Sanctum.

## What to add

Add the original reference photos with the highest available resolution. Prefer:
- 3 or more overlapping views of the same architecture.
- Photos taken from different positions, not only crops of one photo.
- Original EXIF metadata when available.
- Views that cover entrances, nave, windows, roof, towers and interior landmarks.
- A separate note for any trusted real-world measurement, such as a door width/height or known wall length.

## What not to use as geometry authority

Do not use AI-upscaled, perspective-warped, heavily edited or generated images as geometry authority unless the original is also present. They can still be visual references.

## Automatic worker

When 3+ supported images are committed here, the XZIEL reference-reconstruction workflow runs pyCOLMAP on CPU, recovers cameras and a sparse point cloud, cleans the cloud with Open3D and uploads:
- reconstructed camera intrinsics/extrinsics
- raw and cleaned sparse PLY point clouds
- image SHA-256 hashes
- reconstruction quality statistics

The resulting SfM coordinate system has arbitrary scale. The report intentionally keeps \`metric_scale_known=false\` until a trusted real-world measurement is applied. This prevents a visually good reconstruction from being mislabeled as a true metric 1:1 copy.
