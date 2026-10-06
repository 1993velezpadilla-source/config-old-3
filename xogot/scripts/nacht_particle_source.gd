extends RefCounted

## Source-value decoder for the UE4.21 Cascade authority JSON.
##
## The extractor intentionally preserves provenance wrappers such as
## FScriptStruct, FStructFallback, UScriptArray, FVector and FPackageIndex.
## Runtime code uses this helper to unwrap those wrappers without guessing
## material/particle semantics.

static func _reflected_members(value: Dictionary) -> Dictionary:
	var raw: Variant = value.get("members", {})
	return raw as Dictionary if raw is Dictionary else {}


static func _fallback_properties(value: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	var raw: Variant = value.get("properties", [])
	if not (raw is Array):
		return result
	for item: Variant in raw:
		if not (item is Dictionary):
			continue
		var row := item as Dictionary
		var name := str(row.get("name", ""))
		if name.is_empty():
			continue
		result[name] = unwrap(row.get("value"))
	return result


static func _reflected_property_value(value: Dictionary) -> Variant:
	var members := _reflected_members(value)
	if members.has("GenericValue"):
		return unwrap(members["GenericValue"])
	if members.has("Value"):
		return unwrap(members["Value"])
	return null


static func _reflected_array(value: Dictionary) -> Array:
	var members := _reflected_members(value)
	var raw_properties: Variant = members.get("Properties", [])
	if not (raw_properties is Array):
		return []
	var result: Array = []
	for item: Variant in raw_properties:
		if item is Dictionary:
			var decoded: Variant = _reflected_property_value(item as Dictionary)
			if decoded != null:
				result.append(decoded)
			else:
				result.append(unwrap(item))
		else:
			result.append(unwrap(item))
	return result


static func unwrap(value: Variant) -> Variant:
	if value is Array:
		var result: Array = []
		for item: Variant in value:
			result.append(unwrap(item))
		return result
	if not (value is Dictionary):
		return value

	var row := value as Dictionary
	var kind := str(row.get("kind", ""))

	if kind == "FScriptStruct":
		return unwrap(row.get("value"))
	if kind == "FStructFallback":
		return _fallback_properties(row)
	if kind == "FPackageIndex":
		return row.get("path")
	if kind.ends_with(".UScriptArray"):
		return _reflected_array(row)
	if kind.ends_with(".FName"):
		var name_members := _reflected_members(row)
		return str(name_members.get("Text", name_members.get("PlainText", "")))
	if kind.ends_with(".FVector") or kind.ends_with(".FVector2D") or kind.ends_with(".FVector4"):
		var vector_members := _reflected_members(row)
		var decoded_vector: Dictionary = {}
		for key: Variant in vector_members.keys():
			decoded_vector[str(key)] = unwrap(vector_members[key])
		return decoded_vector

	var members := _reflected_members(row)
	if not members.is_empty():
		# Property wrappers expose both Value and GenericValue. Prefer the
		# latter because it is the canonical CUE4Parse accessor.
		if members.has("GenericValue"):
			return unwrap(members["GenericValue"])
		if members.has("Value") and members.size() <= 4:
			return unwrap(members["Value"])
		var decoded_members: Dictionary = {}
		for key: Variant in members.keys():
			decoded_members[str(key)] = unwrap(members[key])
		return decoded_members

	var decoded: Dictionary = {}
	for key: Variant in row.keys():
		decoded[str(key)] = unwrap(row[key])
	return decoded


static func properties(node: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	var raw: Variant = node.get("properties", [])
	if not (raw is Array):
		return result
	for item: Variant in raw:
		if not (item is Dictionary):
			continue
		var row := item as Dictionary
		var name := str(row.get("name", ""))
		if name.is_empty():
			continue
		result[name] = unwrap(row.get("value"))
	return result


static func package_path(value: Variant) -> String:
	var decoded: Variant = unwrap(value)
	return str(decoded) if decoded != null else ""


static func vector2(value: Variant, default_value := Vector2.ZERO) -> Vector2:
	var decoded: Variant = unwrap(value)
	if not (decoded is Dictionary):
		return default_value
	var row := decoded as Dictionary
	if not row.has("X") or not row.has("Y"):
		return default_value
	return Vector2(
		float(row.get("X", 0.0)),
		float(row.get("Y", 0.0))
	)


static func vector3(value: Variant, default_value := Vector3.ZERO) -> Vector3:
	var decoded: Variant = unwrap(value)
	if not (decoded is Dictionary):
		return default_value
	var row := decoded as Dictionary
	if not row.has("X") or not row.has("Y") or not row.has("Z"):
		return default_value
	return Vector3(
		float(row.get("X", 0.0)),
		float(row.get("Y", 0.0)),
		float(row.get("Z", 0.0))
	)


static func distribution(value: Variant) -> Dictionary:
	var decoded: Variant = unwrap(value)
	if not (decoded is Dictionary):
		return {}
	var row := decoded as Dictionary
	var result: Dictionary = {}

	for key in [
		"Distribution",
		"MinValue",
		"MaxValue",
		"MinValueVec",
		"MaxValueVec",
	]:
		if row.has(key):
			result[key] = row[key]

	if row.has("Table") and row["Table"] is Dictionary:
		var table := row["Table"] as Dictionary
		result["Table"] = {
			"EntryCount": int(table.get("EntryCount", 0)),
			"EntryStride": int(table.get("EntryStride", 0)),
			"SubEntryStride": int(table.get("SubEntryStride", 0)),
			"Op": int(table.get("Op", 0)),
			"TimeScale": float(table.get("TimeScale", 1.0)),
			"TimeBias": float(table.get("TimeBias", 0.0)),
			"Values": table.get("Values", []),
		}

	return result


static func table_values(distribution_row: Dictionary) -> Array:
	var raw_table: Variant = distribution_row.get("Table", {})
	if not (raw_table is Dictionary):
		return []
	var raw_values: Variant = (raw_table as Dictionary).get("Values", [])
	return raw_values as Array if raw_values is Array else []


static func float_value(value: Variant, default_value := 0.0) -> float:
	var decoded: Variant = unwrap(value)
	if decoded is float or decoded is int:
		return float(decoded)
	if decoded is String:
		var text := str(decoded).strip_edges()
		if text.is_valid_float():
			return text.to_float()
	return float(default_value)


static func table_float_values(distribution_row: Dictionary) -> Array[float]:
	var result: Array[float] = []
	for raw: Variant in table_values(distribution_row):
		var decoded: Variant = unwrap(raw)
		if decoded is float or decoded is int:
			result.append(float(decoded))
			continue
		var text := str(decoded).strip_edges()
		if not text.is_valid_float():
			return []
		result.append(text.to_float())
	return result


static func find_system(graphs: Dictionary, object_path: String) -> Dictionary:
	for raw: Variant in graphs.get("systems", []):
		if not (raw is Dictionary):
			continue
		var system := raw as Dictionary
		if str(system.get("objectPath", "")) == object_path:
			return system
	return {}


static func nodes_by_type(system: Dictionary, export_type: String) -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for raw: Variant in system.get("nodes", []):
		if not (raw is Dictionary):
			continue
		var node := raw as Dictionary
		if str(node.get("exportType", "")) == export_type:
			result.append(node)
	return result
