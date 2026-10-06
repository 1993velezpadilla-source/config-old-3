#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/maps/UEStaticSceneExtract/Program.cs")
text = path.read_text(encoding="utf-8-sig")

needle = """var nativeMeshes = new Dictionary<string, NativeMesh>(
    StringComparer.OrdinalIgnoreCase);
"""
replacement = needle + """
var nativeMeshesCanonical = new Dictionary<string, NativeMesh>(
    StringComparer.OrdinalIgnoreCase);
"""
if needle not in text:
    raise SystemExit("native mesh dictionary anchor missing")
text = text.replace(needle, replacement, 1)

needle = """    if (!nativeMeshes.TryAdd(
            objectPath,
            new NativeMesh(
                objectPath,
                file,
                sourceIndex,
                sourceMaterialCount,
                sourceSectionMaterialIndices)))
    {
        throw new InvalidDataException(
            "duplicate XZMS objectPath: " + objectPath);
    }
"""
replacement = """    var nativeRow = new NativeMesh(
        objectPath,
        file,
        sourceIndex,
        sourceMaterialCount,
        sourceSectionMaterialIndices);

    if (!nativeMeshes.TryAdd(objectPath, nativeRow))
    {
        throw new InvalidDataException(
            "duplicate XZMS objectPath: " + objectPath);
    }

    var canonicalObjectPath = CanonicalObjectPath(objectPath);
    if (!nativeMeshesCanonical.TryAdd(canonicalObjectPath, nativeRow))
    {
        var existing = nativeMeshesCanonical[canonicalObjectPath];
        if (!string.Equals(
                existing.ObjectPath,
                objectPath,
                StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException(
                "duplicate canonical XZMS objectPath: " +
                canonicalObjectPath);
        }
    }
"""
if needle not in text:
    raise SystemExit("native mesh add block missing")
text = text.replace(needle, replacement, 1)

needle = """var nullMeshComponents = 0;
var nonFiniteMatrices = 0;
"""
replacement = """var nullMeshComponents = 0;
var loadedMeshComponents = 0;
var resolvedMeshReferenceComponents = 0;
var nonFiniteMatrices = 0;
"""
if needle not in text:
    raise SystemExit("counter anchor missing")
text = text.replace(needle, replacement, 1)

needle = """                var mesh = component.GetLoadedStaticMesh();
                if (mesh is null)
                {
                    nullMeshComponents++;
                    continue;
                }

                var meshPath = mesh.GetPathName();
                if (!nativeMeshes.TryGetValue(
                        meshPath,
                        out var nativeMesh))
                {
                    unresolvedMeshes.Add(meshPath);
                    continue;
                }
"""
replacement = """                var mesh = component.GetLoadedStaticMesh();
                string? meshPath = null;

                if (mesh is not null)
                {
                    loadedMeshComponents++;
                    meshPath = mesh.GetPathName();
                }
                else
                {
                    var meshReference = component.GetStaticMesh();
                    if (!meshReference.IsNull)
                    {
                        meshPath =
                            meshReference.ResolvedObject?.GetPathName();
                        if (!string.IsNullOrWhiteSpace(meshPath))
                            resolvedMeshReferenceComponents++;
                    }
                }

                if (string.IsNullOrWhiteSpace(meshPath))
                {
                    nullMeshComponents++;
                    continue;
                }

                NativeMesh? nativeMesh = null;
                if (!nativeMeshes.TryGetValue(meshPath, out nativeMesh))
                {
                    nativeMeshesCanonical.TryGetValue(
                        CanonicalObjectPath(meshPath),
                        out nativeMesh);
                }

                if (nativeMesh is null)
                {
                    unresolvedMeshes.Add(meshPath);
                    continue;
                }
"""
if needle not in text:
    raise SystemExit("mesh resolution block missing")
text = text.replace(needle, replacement, 1)

needle = """        nullMeshComponents,
        componentsWithMaterialOverrides,
"""
replacement = """        nullMeshComponents,
        loadedMeshComponents,
        resolvedMeshReferenceComponents,
        componentsWithMaterialOverrides,
"""
if needle not in text:
    raise SystemExit("summary counter anchor missing")
text = text.replace(needle, replacement, 1)

marker = """static string NormalizeMergedShardPath(string path)
"""
helper = r"""static string CanonicalObjectPath(string value)
{
    var path = value.Replace('\\', '/');

    var pavlovContent = path.IndexOf(
        "/Pavlov/Content/",
        StringComparison.OrdinalIgnoreCase);
    if (pavlovContent >= 0)
    {
        path = "/Game/" + path[
            (pavlovContent + "/Pavlov/Content/".Length)..];
    }
    else if (path.StartsWith(
        "Pavlov/Content/",
        StringComparison.OrdinalIgnoreCase))
    {
        path = "/Game/" + path["Pavlov/Content/".Length..];
    }
    else
    {
        var content = path.IndexOf(
            "/Content/",
            StringComparison.OrdinalIgnoreCase);
        if (content >= 0 &&
            !path.StartsWith("/Game/", StringComparison.OrdinalIgnoreCase))
        {
            path = "/Game/" + path[
                (content + "/Content/".Length)..];
        }
    }

    return path.Trim();
}

"""
if marker not in text:
    raise SystemExit("canonical helper insertion anchor missing")
text = text.replace(marker, helper + marker, 1)

path.write_text(text, encoding="utf-8")
print("XZOGOT_UE421_STATIC_SCENE_REFERENCE_PATCH_GREEN")
