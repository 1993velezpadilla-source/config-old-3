extends Node3D
## Original Black Pines 3x3 architectural routing graph (not a navmesh).
## Reads EXACT same 12 portal coordinates as Blender/Godot collisions.
## Closed doors are not traversable. Only this map instantiates this script.
const SOURCE := "res://data/black_pines_layout.json"

var _layout: Dictionary = {}
var _edges: Dictionary = {}
var _centers: Dictionary = {}
var _doors: Array = []
var _ready_contract: bool = false

func _ready() -> void:
    var raw: Variant=JSON.parse_string(FileAccess.get_file_as_string(SOURCE))
    if not raw is Dictionary:
        push_error("BLACK_PINES_ROUTING_RED bad JSON")
        return
    _layout=raw as Dictionary
    var cells: Array=_layout.get("cells",[]) as Array
    _doors=_layout.get("portals",[]) as Array
    if cells.size()!=9 or _doors.size()!=12:
        push_error("BLACK_PINES_ROUTING_RED incorrect graph contract")
        return
    var xs: Array=_layout["cellBoundaries"]["x"] as Array
    var zs: Array=_layout["cellBoundaries"]["z"] as Array
    for cell: Dictionary in cells:
        var c: int=int(cell["col"])
        var r: int=int(cell["row"])
        var idx: int=r*3+c
        _edges[idx]=[]
        _centers[idx]=Vector3(
            (float(xs[c])+float(xs[c+1]))*0.5,0.24,
            (float(zs[r])+float(zs[r+1]))*0.5)
    for i in range(_doors.size()):
        var p: Dictionary=_doors[i] as Dictionary
        var a: int=-1
        var b: int=-1
        if str(p["axis"])=="x":
            var row: int=_index_for(float(p["at"]),zs)
            var col: int=_boundary_for(float(p["coord"]),xs)
            a=row*3+col
            b=a+1
        else:
            var row: int=_boundary_for(float(p["coord"]),zs)
            var col: int=_index_for(float(p["at"]),xs)
            a=row*3+col
            b=a+3
        if not _edges.has(a) or not _edges.has(b):
            push_error("BLACK_PINES_ROUTING_RED invalid portal "+str(i))
            return
        _edges[a].append({"to":b,"portal":i})
        _edges[b].append({"to":a,"portal":i})
    _ready_contract=true
    add_to_group("zombie_path_network")
    print("BLACK_PINES_ROUTING_GRAPH_READY cells=9 portals=12 independent=true")

func _index_for(value: float, breaks: Array) -> int:
    for i in range(breaks.size()-1):
        if value < float(breaks[i+1]):
            return i
    return breaks.size()-2

func _boundary_for(value: float, breaks: Array) -> int:
    for i in range(1,breaks.size()-1):
        if absf(value-float(breaks[i]))<0.01:
            return i-1
    return -99

func get_cell_id(world: Vector3) -> int:
    if not _ready_contract:
        return -1
    var xs: Array=_layout["cellBoundaries"]["x"] as Array
    var zs: Array=_layout["cellBoundaries"]["z"] as Array
    if world.x<float(xs[0]) or world.x>float(xs[xs.size()-1]) or (
            world.z<float(zs[0]) or world.z>float(zs[zs.size()-1])):
        return -1
    return _index_for(world.z,zs)*3+_index_for(world.x,xs)

func _door_open(i: int) -> bool:
    var door: Node=get_parent().get_node_or_null("Machines/Door_%02d"%i)
    return door!=null and door.has_method("was_used") and bool(door.call("was_used"))

func _portal_route(start_id: int,goal_id: int) -> Array[int]:
    var empty: Array[int]=[]
    if not _ready_contract or start_id<0 or goal_id<0:
        return empty
    if start_id==goal_id:
        return empty
    var visited: Dictionary={start_id:true}
    var prev: Dictionary={}
    var route: Array[int]=[start_id]
    var head: int=0
    while head<route.size():
        var current: int=route[head]
        head+=1
        if current==goal_id:
            break
        for edge_var: Variant in _edges[current]:
            var edge: Dictionary=edge_var as Dictionary
            var nxt: int=int(edge["to"])
            if visited.has(nxt) or not _door_open(int(edge["portal"])):
                continue
            visited[nxt]=true
            prev[nxt]={"from":current,"portal":int(edge["portal"])}
            route.append(nxt)
    if not visited.has(goal_id):
        return empty
    var answer: Array[int]=[]
    var cursor: int=goal_id
    while cursor!=start_id:
        var hop: Dictionary=prev[cursor] as Dictionary
        answer.push_front(int(hop["portal"]))
        cursor=int(hop["from"])
    return answer

func can_reach(from_world: Vector3,to_world: Vector3) -> bool:
    var from_id: int=get_cell_id(from_world)
    var to_id: int=get_cell_id(to_world)
    if from_id<0 or to_id<0:
        return false
    return from_id==to_id or not _portal_route(from_id,to_id).is_empty()

func request_path(from_world: Vector3,to_world: Vector3) -> Array[Vector3]:
    var answer: Array[Vector3]=[]
    var start_id: int=get_cell_id(from_world)
    var goal_id: int=get_cell_id(to_world)
    if start_id<0 or goal_id<0:
        return answer
    if start_id==goal_id:
        answer.append(to_world)
        return answer
    var hops: Array[int]=_portal_route(start_id,goal_id)
    if hops.is_empty():
        return answer  # strictly no "walk through locked wall" fallback
    var current: int=start_id
    for i in hops:
        var portal: Dictionary=_doors[i] as Dictionary
        var axis: String=str(portal["axis"])
        var p: Vector3=Vector3(float(portal["coord"]),0.24,float(portal["at"])) if axis=="x" else (
            Vector3(float(portal["at"]),0.24,float(portal["coord"])))
        var base_a: int=-1
        var base_b: int=-1
        for k in _edges[current]:
            if int((k as Dictionary)["portal"])==i:
                base_b=int((k as Dictionary)["to"])
                base_a=current
                break
        if base_b<0:
            return []
        var delta: Vector3=Vector3.RIGHT if axis=="x" else Vector3.BACK
        var sign: float=1.0 if base_b>base_a else -1.0
        answer.append(p-delta*sign*1.12)
        answer.append(p+delta*sign*1.12)
        current=base_b
    answer.append(to_world)
    return answer

func recovery_point(from_world: Vector3,to_world: Vector3) -> Vector3:
    var route: Array[Vector3]=request_path(from_world,to_world)
    if route.is_empty():
        var cell: int=get_cell_id(from_world)
        return _centers.get(cell,from_world) as Vector3
    for point: Vector3 in route:
        if from_world.distance_to(point)>0.6:
            return point
    return from_world

func get_node_count() -> int:
    return _centers.size()

func get_portal_count() -> int:
    return _doors.size()
