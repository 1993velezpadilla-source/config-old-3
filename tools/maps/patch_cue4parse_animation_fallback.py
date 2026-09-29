#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

PINNED_COMMIT = "28f385e622468c4ab84997d596b46bb1c3adfcfa"

OLD = """            var boneCompressionCodec = BoneCompressionSettings?.Load<UAnimBoneCompressionSettings>()?.GetCodec(BoneCodecDDCHandle);
            if (boneCompressionCodec != null)
            {
                CompressedDataStructure = boneCompressionCodec.AllocateAnimData();
                CompressedDataStructure.SerializeCompressedData(Ar);
                CompressedDataStructure.Bind(serializedByteStream);
                NumFrames = CompressedDataStructure.CompressedNumberOfFrames;
            }
            else if (serializedByteStream.Length > 0)
            {
                Log.Warning("Unknown bone compression codec {0}", BoneCodecDDCHandle);
            }
"""

NEW = """            var boneCompressionCodec = BoneCompressionSettings?.Load<UAnimBoneCompressionSettings>()?.GetCodec(BoneCodecDDCHandle);
            if (boneCompressionCodec != null)
            {
                CompressedDataStructure = boneCompressionCodec.AllocateAnimData();
                CompressedDataStructure.SerializeCompressedData(Ar);
                CompressedDataStructure.Bind(serializedByteStream);
                NumFrames = CompressedDataStructure.CompressedNumberOfFrames;
            }
            else if (TryAllocateStandardMissingSettingsCodec(BoneCodecDDCHandle, out var standardCompressedData))
            {
                // Some cooked distributions omit the Engine default compression-settings asset
                // while retaining standard UE codec handles and the complete compressed stream.
                // These two codecs both allocate FUECompressedAnimData in CUE4Parse. Keep this
                // fallback intentionally narrow and fail closed for every other codec family.
                CompressedDataStructure = standardCompressedData;
                CompressedDataStructure.SerializeCompressedData(Ar);
                CompressedDataStructure.Bind(serializedByteStream);
                NumFrames = CompressedDataStructure.CompressedNumberOfFrames;
                Log.Warning("Using standard missing-settings animation codec fallback for {0}", BoneCodecDDCHandle);
            }
            else if (serializedByteStream.Length > 0)
            {
                Log.Warning("Unknown bone compression codec {0}", BoneCodecDDCHandle);
            }
"""

HELPER_ANCHOR = """        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        private static byte[] ReadSerializedByteStream(FAssetArchive Ar)
"""

HELPER = """        private static bool TryAllocateStandardMissingSettingsCodec(
            string? ddcHandle,
            out ICompressedAnimData compressedData)
        {
            compressedData = null!;

            if (string.IsNullOrWhiteSpace(ddcHandle))
                return false;

            var separator = ddcHandle.LastIndexOf('_');
            if (separator <= 0 || separator + 1 >= ddcHandle.Length)
                return false;

            var suffix = ddcHandle.AsSpan(separator + 1);
            for (var i = 0; i < suffix.Length; i++)
            {
                if (!char.IsDigit(suffix[i]))
                    return false;
            }

            var family = ddcHandle[..separator];
            if (!family.Equals(
                    "AnimCompress_PerTrackCompression",
                    StringComparison.Ordinal) &&
                !family.Equals(
                    "AnimCompress_RemoveLinearKeys",
                    StringComparison.Ordinal))
            {
                return false;
            }

            compressedData = new FUECompressedAnimData();
            return true;
        }

"""

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    source = root / "CUE4Parse" / "UE4" / "Assets" / "Exports" / "Animation" / "UAnimSequence.cs"
    if not source.is_file():
        raise SystemExit(f"missing CUE4Parse source: {source}")

    text = source.read_text(encoding="utf-8-sig")

    if "TryAllocateStandardMissingSettingsCodec" in text:
        print("XZIEL_CUE4PARSE_ANIMATION_FALLBACK_ALREADY_PATCHED")
        return 0

    if OLD not in text:
        raise SystemExit("pinned CUE4Parse animation codec block did not match; refusing to patch")

    text = text.replace(OLD, NEW, 1)

    if HELPER_ANCHOR not in text:
        raise SystemExit("pinned CUE4Parse helper anchor did not match; refusing to patch")

    text = text.replace(HELPER_ANCHOR, HELPER + HELPER_ANCHOR, 1)
    source.write_text(text, encoding="utf-8")

    print("XZIEL_CUE4PARSE_ANIMATION_FALLBACK_GREEN", {
        "commit": PINNED_COMMIT,
        "source": str(source),
        "families": [
            "AnimCompress_PerTrackCompression_*",
            "AnimCompress_RemoveLinearKeys_*",
        ],
    })
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
