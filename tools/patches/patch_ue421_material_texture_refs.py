#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/maps/UEMaterialAudit/Program.cs")
text = path.read_text(encoding="utf-8-sig")

old = r'''                var textures = new List<object>();
                foreach (var textureEntry in parameters.Textures
                             .OrderBy(
                                 row => row.Key,
                                 StringComparer.Ordinal))
                {
                    textureReferenceCount++;

                    if (textureEntry.Value is UTexture texture)
                    {
                        textureLoadCount++;
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = texture.GetPathName(),
                            exportType = texture.ExportType,
                            loaded = true
                        });
                    }
                    else
                    {
                        var unresolved = new
                        {
                            materialPath = material.GetPathName(),
                            parameter = textureEntry.Key,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        };
                        unresolvedTextureRefs.Add(unresolved);
                        textures.Add(new
                        {
                            parameter = textureEntry.Key,
                            objectPath = (string?)null,
                            exportType = (string?)null,
                            loaded = false,
                            reference =
                                textureEntry.Value.ToString(),
                            referenceType =
                                textureEntry.Value.GetType().FullName
                        });
                    }
                }
'''

new = r'''                var textureTruth =
                    ResolveAuthoritativeTextureReferences(
                        material,
                        provider);

                // CMaterialParams2 still contributes expression/cached texture
                // references when available. Cooked UE4.21 MaterialInstance
                // parents often fail provider-side loading, so the explicit
                // TextureParameterValues resolver above is the authority for
                // those instances and parent chains.
                foreach (var textureEntry in parameters.Textures)
                {
                    var key = textureEntry.Key;
                    if (textureEntry.Value is UTexture loadedTexture)
                    {
                        textureTruth[key] = new TextureTruth(
                            key,
                            loadedTexture.GetPathName(),
                            loadedTexture.ExportType,
                            true,
                            loadedTexture.GetPathName(),
                            loadedTexture.GetType().FullName);
                    }
                    else if (textureEntry.Value is not null &&
                             !textureTruth.ContainsKey(key))
                    {
                        var reference = textureEntry.Value.ToString();
                        textureTruth[key] = new TextureTruth(
                            key,
                            textureEntry.Value.GetPathName(),
                            textureEntry.Value.ExportType,
                            false,
                            reference,
                            textureEntry.Value.GetType().FullName);
                    }
                }

                var textures = new List<object>();
                foreach (var pair in textureTruth
                             .OrderBy(
                                 row => row.Key,
                                 StringComparer.Ordinal))
                {
                    var truth = pair.Value;
                    textureReferenceCount++;

                    if (truth.Loaded)
                        textureLoadCount++;

                    if (string.IsNullOrWhiteSpace(truth.ObjectPath))
                    {
                        unresolvedTextureRefs.Add(new
                        {
                            materialPath = material.GetPathName(),
                            parameter = truth.Parameter,
                            reference = truth.Reference,
                            referenceType = truth.ReferenceType
                        });
                    }

                    textures.Add(new
                    {
                        parameter = truth.Parameter,
                        objectPath = truth.ObjectPath,
                        exportType = truth.ExportType,
                        loaded = truth.Loaded,
                        reference = truth.Reference,
                        referenceType = truth.ReferenceType
                    });
                }
'''

if old not in text:
    raise SystemExit("texture collection block missing")
text = text.replace(old, new, 1)

anchor = r'''static (
    bool resolved,
'''
helper = r'''static Dictionary<string, TextureTruth>
ResolveAuthoritativeTextureReferences(
    UUnrealMaterial material,
    DefaultFileProvider provider,
    HashSet<string>? visiting = null)
{
    visiting ??= new HashSet<string>(
        StringComparer.OrdinalIgnoreCase);

    var result = new Dictionary<string, TextureTruth>(
        StringComparer.Ordinal);
    var materialPath = material.GetPathName();
    if (!visiting.Add(materialPath))
        return result;

    try
    {
        if (material is UMaterialInstance instance)
        {
            UUnrealMaterial? parent = instance.Parent;

            if (parent is null)
            {
                var rawParentProperty =
                    instance.Properties.FirstOrDefault(
                        p => p.Name.Text.Equals(
                            "Parent",
                            StringComparison.Ordinal));

                if (rawParentProperty?.Tag?.GenericValue
                        is FPackageIndex rawParent &&
                    !rawParent.IsNull)
                {
                    if (rawParent.TryLoad<UUnrealMaterial>(
                            out var rawLoadedParent) &&
                        rawLoadedParent is not null &&
                        rawLoadedParent != material)
                    {
                        parent = rawLoadedParent;
                    }
                    else
                    {
                        parent = ResolveMaterialByRawReference(
                            provider,
                            rawParent.ResolvedObject?.GetPathName()
                                ?? rawParent.ToString());
                    }
                }
            }

            if (parent is not null && parent != material)
            {
                foreach (var inherited in
                         ResolveAuthoritativeTextureReferences(
                             parent,
                             provider,
                             visiting))
                {
                    result[inherited.Key] = inherited.Value;
                }
            }
        }

        if (material is UMaterialInstanceConstant constant)
        {
            foreach (var parameter in
                     constant.TextureParameterValues)
            {
                var reference = parameter.ParameterValue;
                if (reference is null || reference.IsNull)
                    continue;

                UTexture? loaded = null;
                reference.TryLoad<UTexture>(out loaded);

                var objectPath =
                    loaded?.GetPathName()
                    ?? reference.ResolvedObject?.GetPathName();

                var name = parameter.Name;
                result[name] = new TextureTruth(
                    name,
                    objectPath,
                    loaded?.ExportType,
                    loaded is not null,
                    reference.ToString(),
                    reference.GetType().FullName);
            }
        }

        return result;
    }
    finally
    {
        visiting.Remove(materialPath);
    }
}

'''
if anchor not in text:
    raise SystemExit("helper insertion anchor missing")
text = text.replace(anchor, helper + anchor, 1)

if "sealed record TextureTruth(" not in text:
    text = text.rstrip() + r"""

sealed record TextureTruth(
    string Parameter,
    string? ObjectPath,
    string? ExportType,
    bool Loaded,
    string? Reference,
    string? ReferenceType);
""" + "\n"

path.write_text(text, encoding="utf-8")
print("XZOGOT_UE421_MATERIAL_TEXTURE_REFERENCE_PATCH_GREEN")
