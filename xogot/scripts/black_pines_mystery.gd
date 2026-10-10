extends "res://scripts/interactable.gd"
## Black Pines original DESIGN-lab box: real pre-existing weapon reward system,
## spatially moves between four authored positions after four paid spins.
## Not represented as an exact Treyarch/BO3 source-script reconstruction.
@export var locations: Array = []
@export var spins_before_move: int = 4
@export var relocation_delay: float = 1.65

var _spot_index: int = 0
var _spins_here: int = 0
var _relocating: bool = false
var _total_paid_spins: int = 0

func _ready() -> void:
    super._ready()
    if locations.size()<2:
        push_error("BLACK_PINES_MYSTERY_RED at least two original independent authored spots required")
    set_meta("black_pines_box_original_contract_not_source_game",true)
    set_meta("black_pines_mystery_location_index",_spot_index)

func interact(player: Node) -> bool:
    if _relocating:
        return false
    var before: int=get_interaction_count()
    var points_before: int=int(player.call("get_points")) if player!=null and player.has_method("get_points") else -1
    var ok: bool=super.interact(player)
    if not ok or get_interaction_count()!=before+1:
        return false
    if get_last_result().is_empty():
        # A failed weapon grant must never silently charge the player.
        if player!=null and player.has_method("add_points") and points_before>=0:
            var spent: int=points_before-int(player.call("get_points"))
            if spent>0:
                player.call("add_points",spent)
        push_error("BLACK_PINES_MYSTERY_RED empty weapon result; transaction refunded")
        return false
    _spins_here+=1
    _total_paid_spins+=1
    set_meta("black_pines_paid_spins",_total_paid_spins)
    if _spins_here>=spins_before_move:
        _relocating=true
        _schedule_move()
    return true

func _schedule_move() -> void:
    await get_tree().create_timer(relocation_delay).timeout
    if not is_inside_tree() or locations.size()<2:
        return
    var visuals: Node3D=get_node_or_null("MysteryChest") as Node3D
    var collision: CollisionShape3D=get_node_or_null("CollisionShape3D") as CollisionShape3D
    if visuals!=null:
        visuals.visible=false
    if collision!=null:
        collision.set_deferred("disabled",true)
    await get_tree().create_timer(0.35).timeout
    _spot_index=(_spot_index+1)%locations.size()
    var loc: Array=locations[_spot_index] as Array
    global_position=Vector3(float(loc[0]),float(loc[1])+0.62,float(loc[2]))
    if visuals!=null:
        visuals.visible=true
    if collision!=null:
        collision.set_deferred("disabled",false)
    _spins_here=0
    _relocating=false
    set_meta("black_pines_mystery_location_index",_spot_index)
    print("BLACK_PINES_MYSTERY_RELOCATED spot=",_spot_index,
        " spins=",_total_paid_spins," network_4P_certified=false")

func get_black_pines_location_index() -> int:
    return _spot_index

func get_black_pines_total_paid_spins() -> int:
    return _total_paid_spins
