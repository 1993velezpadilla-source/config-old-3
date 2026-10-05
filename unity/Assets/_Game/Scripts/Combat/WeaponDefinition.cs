using UnityEngine;
namespace Sanctum.Zombies.Combat {
 public enum WeaponFireMode{SemiAuto,FullAuto,Pump,Bolt,Revolver} public enum WeaponClass{Pistol,SMG,Rifle,Shotgun,LMG,Sniper}
 [CreateAssetMenu(menuName="Sanctum/Weapon Definition")] public sealed class WeaponDefinition:ScriptableObject{
  public string weaponId,displayName;public WeaponClass weaponClass;public WeaponFireMode fireMode;public GameObject viewModelPrefab;public RuntimeAnimatorController viewModelAnimatorController;
  public float baseDamage=30,packAPunchDamage=70,falloffStartMeters=12,falloffEndMeters=35,minimumFalloffMultiplier=.55f,headMultiplier=2,limbMultiplier=.72f;
  public int pellets=1,magazineSize=30,packAPunchMagazineSize=60,startingReserve=180;public float roundsPerMinute=600,maxRangeMeters=120,hipSpreadDegrees=1.6f,adsSpreadDegrees=.25f;
  public Vector3 hipLocalPosition=new(.16f,-.19f,.34f),hipLocalEuler,adsLocalPosition=new(0,-.095f,.19f),adsLocalEuler;public float adsFieldOfView=58,adsSpeed=14;
  public float SecondsPerShot=>60f/Mathf.Max(1,roundsPerMinute);public int MagazineFor(bool p)=>p?Mathf.Max(magazineSize,packAPunchMagazineSize):magazineSize;public float DamageFor(bool p)=>p?packAPunchDamage:baseDamage;
 }
}