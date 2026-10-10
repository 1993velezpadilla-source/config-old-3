"""BLACK PINES - original authored hospital hero prop kit.

No ripped/source-game meshes, fonts, external PBR or subscriptions.
Unique focal shapes per ward, mobile-limited geometry; noncolliding visuals
only pending separate collision/nav acceptance. All component positions use
the shared manifest Godot X,Y,Z layout (Blender bridge owns axis conversion).
"""
import bpy

HERO_COMPONENTS = {}
# Nine original focal props. CI audits THESE live Blender meshes and Godot GLB.
ROOM_HERO_IDS = {
    "generator": "Forge_Hero_GeneratorControlDesk",
    "isolation": "Forge_Hero_IsolationNegativePressureUnit",
    "surgery": "Forge_Hero_SurgeryAnesthesiaCart",
    "patients": "Forge_Hero_PatientWardSupplyCabinet",
    "triage": "Forge_Hero_TriageEmergencyCrashCart",
    "cafeteria": "Forge_Hero_CafeteriaColdStorage",
    "security": "Forge_Hero_SecuritySwitchboard",
    "yard": "Forge_Hero_AmbulanceEmergencyLight",
    "garage": "Forge_Hero_GarageHydraulicCompressor",
}


def build(api, layout, box, tube):
    HERO_COMPONENTS.clear()

    def piece(room, name, position, dimensions, material, round_edge=.022):
        obj = box(api, name, position, dimensions, material, round_edge, "prop")
        HERO_COMPONENTS.setdefault(room, []).append(obj.name)
        return obj

    def pipe(room, name, start, end, radius, material, sides=9):
        obj = tube(api, name, start, end, radius, material, sides)
        HERO_COMPONENTS.setdefault(room, []).append(obj.name)
        return obj

    # Power shed: legible generator control desk, manual switches and gauges.
    # Safe back corner (-16.7,-12.6), distant from generator-room paid doors.
    piece("generator", "Hero_GeneratorControlDesk",
          (-16.6,.75,-12.9), (1.15,1.42,.46), "dark_metal", .055)
    piece("generator", "GenControl_Front",( -16.58,1.12,-12.58),
          (.92,.70,.055), "industrial",.033)
    for i in range(3):
        x = -16.87 + .29*i
        piece("generator", "GenControl_MeterFace_%d"%i,
              (x,1.29,-12.52),(.18,.18,.018),"ice",.016)
        pipe("generator", "GenControl_Toggle_%d"%i,
             (x,1.02,-12.46),(x,.92,-12.41),.019,"brass")
    pipe("generator", "GenControl_Cable",(-16.45,.30,-12.9),
         (-16.45,.30,-11.45),.055,"dark_metal",7)

    # Isolation ward: cleanly recognizable negative-pressure ventilation.
    piece("isolation", "Hero_IsolationNegativePressureUnit",
          (-5.75,1.13,-12.85),(.42,2.14,1.32),"medical",.09)
    piece("isolation", "Isolation_FilterFront",
          (-5.50,1.52,-12.85),(.048,.61,1.0),"dark_metal",.018)
    for i in range(4):
        y=1.31 + .13*i
        piece("isolation", "Isolation_FilterSlat_%d"%i,
              (-5.47,y,-12.85),(.049,.034,.92),"brass",.008)
    piece("isolation", "Isolation_Alarm",
          (-5.49,2.00,-12.85),(.06,.13,.17),"red",.014)
    pipe("isolation", "Isolation_CeilingIntake",
         (-5.81,2.25,-12.85),(-5.81,3.35,-12.85),.085,"industrial")
    pipe("isolation", "Isolation_CeilingBranch",
         (-5.81,3.35,-12.85),(-4.65,3.35,-12.85),.085,"industrial")

    # Surgery: compact anesthetic trolley next to the operating table.
    piece("surgery", "Hero_SurgeryAnesthesiaCart",
          (16.55,.70,-12.90),(.72,1.36,.60),"medical",.08)
    for i in range(2):
        piece("surgery", "Surgery_EquipmentDrawer_%d"%i,
              (16.55,.48+.36*i,-12.575),(.57,.25,.035),"dark_metal",.012)
    piece("surgery", "Surgery_CartScreen",
          (16.55,1.49,-12.75),(.62,.47,.12),"dark_metal",.035)
    piece("surgery", "Surgery_CartScreenPixel",
          (16.55,1.49,-12.675),(.53,.37,.018),"ice",.012)
    for x in (16.30,16.80):
        for z in (-13.11,-12.69):
            piece("surgery", "Surgery_RubberCastor_%.2f_%.2f"%(x,z),
                  (x,.11,z),(.17,.20,.13),"dark_metal",.041)
    pipe("surgery", "Surgery_SuctionTube",
         (16.78,1.35,-12.75),(16.48,1.96,-12.75),.021,"brass",7)

    # Patient wing: emergency supplies, glass/metal front; four real bed
    # silhouettes are authored by black_pines_author.py already.
    piece("patients", "Hero_PatientWardSupplyCabinet",
          (-16.62,1.15,7.50),(.55,2.14,1.24),"medical",.065)
    piece("patients", "Ward_CabinetGlass",
          (-16.31,1.56,7.50),(.035,.80,.96),"dark_glass",.014)
    for i in range(3):
        piece("patients", "Ward_StorageShelf_%d"%i,
              (-16.30,.51+.27*i,7.50),(.05,.048,1.08),"brass",.008)
    piece("patients", "Ward_FirstAidBadge",
          (-16.29,2.04,7.50),(.055,.22,.26),"red",.011)

    # Triage: visibly medical rather than a single 4m reception block.
    piece("triage", "Hero_TriageEmergencyCrashCart",
          (-5.64,.53,7.40),(.62,1.02,.60),"red",.085)
    for i in range(3):
        piece("triage", "Triage_Drawer_%d"%i,
              (-5.64,.32+.255*i,7.74),(.49,.18,.040),"dark_metal",.015)
    piece("triage", "Triage_ResuscitationPanel",
          (-5.64,1.19,7.40),(.63,.29,.49),"medical",.037)
    piece("triage", "Triage_WhiteCarryHandle",
          (-5.64,1.34,7.40),(.38,.045,.12),"brass",.019)
    for x in (-5.85,-5.43):
        for z in (7.16,7.64):
            piece("triage", "Triage_Castor_%.2f_%.2f"%(x,z),
                  (x,.105,z),(.12,.18,.12),"dark_metal",.040)

    # Mess hall: cold storage + institutional door seam + indicator.
    piece("cafeteria", "Hero_CafeteriaColdStorage",
          (16.59,1.14,7.65),(.69,2.20,1.15),"industrial",.079)
    piece("cafeteria", "Cafeteria_LockerInset",
          (16.18,1.30,7.64),(.024,1.39,.97),"medical",.021)
    pipe("cafeteria", "Cafeteria_Handle",
         (16.13,1.24,7.17),(16.13,1.24,7.43),.024,"brass")
    piece("cafeteria", "Cafeteria_Thermostat",
          (16.13,2.01,7.36),(.025,.12,.19),"ice",.009)
    for i in range(3):
        piece("cafeteria", "Cafeteria_Louver_%d"%i,
              (16.14,.31+.09*i,7.64),(.025,.04,.88),"dark_metal",.006)

    # Security: wall mounted dispatch switchboard and worn manual controls.
    piece("security", "Hero_SecuritySwitchboard",
          (-16.87,1.59,18.76),(.25,1.17,1.74),"dark_metal",.026)
    for i in range(3):
        z=18.27+.46*i
        piece("security", "Security_CCTVGlass_%d"%i,
              (-16.71,1.76,z),(.027,.34,.39),"dark_glass",.011)
        piece("security", "Security_Lockout_%d"%i,
              (-16.70,1.30,z),(.03,.13,.14),"red",.009)
    pipe("security", "Security_ArmoredConduit",
         (-17.0,2.22,18.76),(-17.0,3.10,18.76),
         .074,"industrial",8)

    # Exterior emergency beacon raised above the original ambulance shell.
    piece("yard", "Hero_AmbulanceEmergencyLight",
          (3.80,2.24,17.80),(1.32,.18,.48),"dark_metal",.053)
    for i,(x,kind) in enumerate(((3.43,"red"),(3.80,"ice"),(4.17,"red"))):
        piece("yard", "Yard_AmbulanceBeacon_%d"%i,
              (x,2.39,17.80),(.28,.20,.34),kind,.069)
    piece("yard", "Yard_AmbulanceHoodBadge",
          (6.28,1.31,17.80),(.05,.21,.52),"brass",.027)

    # Garage: hydraulic compressor with original copper tubing and motor.
    piece("garage", "Hero_GarageHydraulicCompressor",
          (16.14,.65,18.80),(.89,1.25,.69),"rust",.081)
    piece("garage", "Garage_CompressorMotor",
          (15.69,.85,18.80),(.53,.69,.60),"dark_metal",.096)
    pipe("garage", "Garage_PressureNeedle",
         (15.92,1.34,18.80),(15.92,1.95,18.80),
         .036,"brass",8)
    pipe("garage", "Garage_PressureHose",
         (15.92,1.87,18.80),(15.92,1.87,19.50),
         .036,"industrial",8)
    piece("garage", "Garage_CompressorFoot",
          (16.14,.12,18.80),(1.03,.20,.86),"dark_metal",.037)

    assert set(HERO_COMPONENTS) == {str(c["id"]) for c in layout["cells"]}
    return {
        "roomHeroes": {k:ROOM_HERO_IDS[k] for k in sorted(HERO_COMPONENTS)},
        "roomHeroComponents": {k:len(v) for k,v in sorted(HERO_COMPONENTS.items())},
        "originalGeometry":True,
        "cosmeticOnlyUntilCollisionGate":True,
        "mobilePropBatchingNotYetMeasured":True,
    }


def guard(layout):
    problems=[]
    for room,name in ROOM_HERO_IDS.items():
        if bpy.data.objects.get(name) is None:
            problems.append("missing room-specific signature hero in "+room)
        if len(HERO_COMPONENTS.get(room,[]))<4:
            problems.append("insufficient identity hardware for "+room)
    # Single source of truth: the saved Godot collision hull must correspond
    # to the actual unbatched Blender asset, before any export-only joining.
    manifest=layout.get("heroCollisionProxies", [])
    if len(manifest)!=9:
        problems.append("missing original shared hero collision manifest")
    for fixture in manifest:
        label=fixture["visual"]
        obj=bpy.data.objects.get(label)
        if obj is None:
            problems.append("hero collider has no Blender source: "+label)
            continue
        if fixture["id"]=="yard":
            # Court collision surrounds the vehicle shell, not the beacon.
            if bpy.data.objects.get("RustyAmbulanceCab") is None:
                problems.append("yard ambulance collision lacks cab")
            continue
        got=(float(obj.location.x),float(obj.location.z),-float(obj.location.y))
        expected=fixture["center"]
        if any(abs(got[i]-float(expected[i]))>.015 for i in range(3)):
            problems.append("hero collider centroid mismatch "+fixture["id"])
        size=(float(obj.dimensions.x),float(obj.dimensions.z),float(obj.dimensions.y))
        spec=fixture["size"]
        if any(abs(size[i]-float(spec[i]))>.025 for i in range(3)):
            problems.append("hero collider extents mismatch "+fixture["id"])
    return problems
