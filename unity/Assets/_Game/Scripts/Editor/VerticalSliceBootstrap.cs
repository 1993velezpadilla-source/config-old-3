#if UNITY_EDITOR
using System;
using System.IO;
using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using Sanctum.Zombies.AI;
using Sanctum.Zombies.Combat;
using Sanctum.Zombies.Player;
using Sanctum.Zombies.Interaction;
using Sanctum.Zombies.World;

namespace Sanctum.Zombies.EditorTools
{
    public static class VerticalSliceBootstrap
    {
        private const string ScenePath = "Assets/_Game/Scenes/UnityZombiesVerticalSlice.unity";
        private const string ChurchPath = "Assets/_Game/Art/Environment/Church/church_final_architecture.glb";
        private const string NunPath = "Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.gltf";
        private const string TuningPath = "Assets/_Game/Data/ZombieRoundTuning.asset";

        [MenuItem("Zombies/Bootstrap/Build Vertical Slice Scene")]
        public static void Build()
        {
            WeaponCatalogBootstrap.Build();
            Directory.CreateDirectory("Assets/_Game/Scenes");
            Directory.CreateDirectory("Assets/_Game/Prefabs");
            Directory.CreateDirectory("Assets/_Game/Data");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject world = new GameObject("WORLD");
            GameObject churchAsset = AssetDatabase.LoadAssetAtPath<GameObject>(ChurchPath);
            if (churchAsset == null) throw new FileNotFoundException(ChurchPath);

            GameObject church = (GameObject)PrefabUtility.InstantiatePrefab(churchAsset);
            church.name = "Church_RealArchitecture";
            church.transform.SetParent(world.transform, false);

            foreach (MeshFilter filter in church.GetComponentsInChildren<MeshFilter>(true))
            {
                if (filter.sharedMesh == null) continue;
                if (filter.GetComponent<Collider>() == null)
                {
                    MeshCollider collider = filter.gameObject.AddComponent<MeshCollider>();
                    collider.sharedMesh = filter.sharedMesh;
                }
                GameObjectUtility.SetStaticEditorFlags(filter.gameObject, StaticEditorFlags.NavigationStatic | StaticEditorFlags.BatchingStatic);
            }

            NavMeshSurface nav = world.AddComponent<NavMeshSurface>();
            nav.collectObjects = CollectObjects.All;
            nav.useGeometry = NavMeshCollectGeometry.PhysicsColliders;

            GameObject lightingRoot = new GameObject("LIGHTING");
            lightingRoot.AddComponent<LightingQualityDirector>();
            CreateLight(lightingRoot.transform, "Moon", LightType.Directional, new Vector3(48f, -32f, 0f), 0.55f, true, LightingPriority.Critical);
            Light nave = CreateLight(lightingRoot.transform, "NaveWarm", LightType.Point, new Vector3(0f, 3.4f, 2f), 4.0f, true, LightingPriority.Critical);
            nave.range = 14f;
            Light altar = CreateLight(lightingRoot.transform, "AltarWarm", LightType.Point, new Vector3(0f, 2.6f, 12f), 3.2f, true, LightingPriority.Accent);
            altar.range = 10f;
            altar.gameObject.AddComponent<HorrorLightFlicker>();

            GameObject player = new GameObject("PLAYER");
            player.transform.position = new Vector3(0f, 1.0f, -7f);
            CharacterController cc = player.AddComponent<CharacterController>();
            cc.height = 1.76f;
            cc.radius = 0.34f;
            cc.center = new Vector3(0f, 0.88f, 0f);
            player.AddComponent<PlayerTarget>();
            PlayerWallet wallet = player.AddComponent<PlayerWallet>();

            GameObject cameraGo = new GameObject("PlayerCamera");
            cameraGo.transform.SetParent(player.transform, false);
            cameraGo.transform.localPosition = new Vector3(0f, 1.62f, 0f);
            Camera cam = cameraGo.AddComponent<Camera>();
            cam.fieldOfView = 72f;
            cam.nearClipPlane = 0.03f;
            cam.tag = "MainCamera";

            MobileFPSController motor = player.AddComponent<MobileFPSController>();
            motor.Configure(cam);

            GameObject socket = new GameObject("ViewModelSocket");
            socket.transform.SetParent(cameraGo.transform, false);

            WeaponADSController ads = player.AddComponent<WeaponADSController>();
            SetObjectReference(ads, "playerCamera", cam);

            WeaponRuntime weapon = player.AddComponent<WeaponRuntime>();
            SetObjectReference(weapon, "playerCamera", cam);
            SetObjectReference(weapon, "viewModelSocket", socket.transform);
            SetObjectReference(weapon, "adsController", ads);

            PlayerInteractor interactor = player.AddComponent<PlayerInteractor>();
            interactor.Configure(cam, wallet, weapon);

            MobileWeaponInput mobileInput = player.AddComponent<MobileWeaponInput>();
            mobileInput.Configure(weapon, interactor);

            TouchFPSInput touchInput = player.AddComponent<TouchFPSInput>();
            touchInput.Configure(motor, mobileInput, interactor);

            WeaponDefinition mp40 = AssetDatabase.LoadAssetAtPath<WeaponDefinition>("Assets/_Game/Data/Weapons/mp40.asset");
            if (mp40 == null) throw new FileNotFoundException("Generated MP40 definition missing.");
            weapon.Equip(mp40);

            ZombieRoundTuning tuning = AssetDatabase.LoadAssetAtPath<ZombieRoundTuning>(TuningPath);
            if (tuning == null)
            {
                tuning = ScriptableObject.CreateInstance<ZombieRoundTuning>();
                AssetDatabase.CreateAsset(tuning, TuningPath);
            }

            GameObject zombiePrefab = BuildZombiePrefab(tuning);
            CreateSpawnDirector(zombiePrefab, tuning);

            GameObject pap = new GameObject("PackAPunch_Test");
            pap.transform.position = new Vector3(3f, 1f, 8f);
            BoxCollider papCollider = pap.AddComponent<BoxCollider>();
            papCollider.size = new Vector3(1.2f, 2f, 0.8f);
            pap.AddComponent<PackAPunchMachine>();

            nav.BuildNavMesh();

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("UNITY_ZOMBIES VERTICAL SLICE BOOTSTRAP GREEN");
        }

        private static GameObject BuildZombiePrefab(ZombieRoundTuning tuning)
        {
            const string prefabPath = "Assets/_Game/Prefabs/ZombieMonja.prefab";
            GameObject modelAsset = AssetDatabase.LoadAssetAtPath<GameObject>(NunPath);
            if (modelAsset == null) throw new FileNotFoundException(NunPath);

            GameObject root = new GameObject("ZombieMonja");
            GameObject model = (GameObject)PrefabUtility.InstantiatePrefab(modelAsset);
            model.name = "MonjaCleanRig";
            model.transform.SetParent(root.transform, false);
            NormalizeModelHeight(model, root.transform, 1.76f);

            NavMeshAgent agent = root.AddComponent<NavMeshAgent>();
            agent.radius = 0.34f;
            agent.height = 1.76f;
            agent.baseOffset = 0f;
            agent.speed = 1.8f;
            agent.acceleration = 18f;
            agent.angularSpeed = 720f;

            Animator animator = model.GetComponentInChildren<Animator>();
            if (animator == null) animator = model.AddComponent<Animator>();
            animator.runtimeAnimatorController = ZombieAnimatorBootstrap.BuildOrGetController();
            animator.applyRootMotion = false;
            animator.updateMode = AnimatorUpdateMode.Normal;
            animator.cullingMode = AnimatorCullingMode.CullUpdateTransforms;

            ZombieHealth health = root.AddComponent<ZombieHealth>();
            SetObjectReference(health, "tuning", tuning);
            SetObjectReference(health, "animator", animator);
            SetObjectReference(health, "agent", agent);

            ZombieBrain brain = root.AddComponent<ZombieBrain>();
            SetObjectReference(brain, "animator", animator);

            CreateHitbox(root.transform, health, "HB_Head", HitZone.Head, new Vector3(0f, 1.60f, 0f), 0.18f, 0.28f);
            CreateHitbox(root.transform, health, "HB_Torso", HitZone.Torso, new Vector3(0f, 1.08f, 0f), 0.28f, 0.65f);
            CreateHitbox(root.transform, health, "HB_Legs", HitZone.Leg, new Vector3(0f, 0.45f, 0f), 0.25f, 0.75f);

            GameObject prefab = PrefabUtility.SaveAsPrefabAsset(root, prefabPath);
            UnityEngine.Object.DestroyImmediate(root);
            return prefab;
        }

        private static void NormalizeModelHeight(GameObject model, Transform root, float targetHeight)
        {
            Renderer[] renderers = model.GetComponentsInChildren<Renderer>(true);
            if (renderers.Length == 0) throw new InvalidDataException("Monja rig contains no renderers.");

            Bounds bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);

            if (bounds.size.y <= 0.0001f) throw new InvalidDataException("Monja renderer bounds have zero height.");

            float scale = targetHeight / bounds.size.y;
            model.transform.localScale *= scale;

            bounds = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++) bounds.Encapsulate(renderers[i].bounds);

            model.transform.position += Vector3.up * (root.position.y - bounds.min.y);
        }

        private static void CreateHitbox(Transform parent, ZombieHealth owner, string name, HitZone zone, Vector3 pos, float radius, float height)
        {
            GameObject hb = new GameObject(name);
            hb.transform.SetParent(parent, false);
            hb.transform.localPosition = pos;
            CapsuleCollider collider = hb.AddComponent<CapsuleCollider>();
            collider.radius = radius;
            collider.height = height;
            ZombieHitbox hitbox = hb.AddComponent<ZombieHitbox>();
            SetObjectReference(hitbox, "owner", owner);
            SetEnum(hitbox, "zone", (int)zone);
        }

        private static void CreateSpawnDirector(GameObject zombiePrefab, ZombieRoundTuning tuning)
        {
            GameObject directorGo = new GameObject("ROUND_DIRECTOR");
            ZombieSpawnDirector director = directorGo.AddComponent<ZombieSpawnDirector>();
            SetObjectReference(director, "tuning", tuning);
            SetObjectReference(director, "zombiePrefab", zombiePrefab.GetComponent<ZombieBrain>());

            ZombieSpawnPoint[] points = new ZombieSpawnPoint[6];
            Vector3[] positions = {
                new Vector3(-7f,0f,5f), new Vector3(7f,0f,5f), new Vector3(-6f,0f,14f),
                new Vector3(6f,0f,14f), new Vector3(-8f,0f,-2f), new Vector3(8f,0f,-2f)
            };

            for (int i = 0; i < points.Length; i++)
            {
                GameObject go = new GameObject($"ZombieSpawn_{i:00}");
                go.transform.position = positions[i];
                points[i] = go.AddComponent<ZombieSpawnPoint>();
            }

            SerializedObject so = new SerializedObject(director);
            SerializedProperty sp = so.FindProperty("spawnPoints");
            sp.arraySize = points.Length;
            for (int i = 0; i < points.Length; i++) sp.GetArrayElementAtIndex(i).objectReferenceValue = points[i];
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static Light CreateLight(Transform parent, string name, LightType type, Vector3 eulerOrPosition, float intensity, bool shadows, LightingPriority priority)
        {
            GameObject go = new GameObject(name);
            go.transform.SetParent(parent, false);
            Light light = go.AddComponent<Light>();
            light.type = type;
            light.intensity = intensity;
            if (type == LightType.Directional) go.transform.eulerAngles = eulerOrPosition;
            else go.transform.position = eulerOrPosition;
            BudgetedLight budget = go.AddComponent<BudgetedLight>();
            budget.priority = priority;
            budget.wantsShadows = shadows;
            return light;
        }

        private static void SetObjectReference(UnityEngine.Object target, string propertyName, UnityEngine.Object value)
        {
            SerializedObject so = new SerializedObject(target);
            SerializedProperty property = so.FindProperty(propertyName);
            if (property == null) throw new MissingFieldException(target.GetType().Name, propertyName);
            property.objectReferenceValue = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void SetEnum(UnityEngine.Object target, string propertyName, int value)
        {
            SerializedObject so = new SerializedObject(target);
            SerializedProperty property = so.FindProperty(propertyName);
            if (property == null) throw new MissingFieldException(target.GetType().Name, propertyName);
            property.enumValueIndex = value;
            so.ApplyModifiedPropertiesWithoutUndo();
        }
    }
}
#endif
