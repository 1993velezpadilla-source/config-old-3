#include "BlackPinesRoundDirector.h"

ABlackPinesRoundDirector::ABlackPinesRoundDirector()
{
    PrimaryActorTick.bCanEverTick=false;
    bReplicates=true;
}
int32 ABlackPinesRoundDirector::WavePopulation(int32 Wave, int32 Players) const
{
    const int32 W=FMath::Max(1,Wave);
    const int32 P=FMath::Clamp(Players,1,4);
    const int32 Cap=FMath::Max(24,MaxSoloWave)+(P-1)*16;
    if(W>=100) return Cap;
    if(W<10) return 6+(W-1)*3+(P-1)*3;
    const float Mult=P==1?3.f:static_cast<float>(P-1)*6.f;
    return FMath::Clamp(FMath::FloorToInt(24.f+Mult*W*W*.03f),1,Cap);
}
int32 ABlackPinesRoundDirector::ZombieHealth(int32 Wave) const
{
    const int32 W=FMath::Max(1,Wave);
    if(W<=9) return W*100+50;
    if(W>=90) return FMath::Max(950,MaxHealth);
    return FMath::Min(FMath::Max(950,MaxHealth),
        FMath::FloorToInt(950.f*FMath::Pow(1.1f,static_cast<float>(W-9))));
}
bool ABlackPinesRoundDirector::BeginNextRound()
{
    if(!HasAuthority() || AliveCount!=0 || SpawnedThisRound<RoundTotal ||
       CurrentRound==MAX_int32) return false;
    ++CurrentRound;
    RoundTotal=WavePopulation(CurrentRound,PlayerCount);
    SpawnedThisRound=0;
    AliveCount=0;
    return true;
}
bool ABlackPinesRoundDirector::RegisterZombieSpawn()
{
    if(!HasAuthority() || SpawnedThisRound>=RoundTotal ||
       AliveCount>=FMath::Max(1,MaxAlive)) return false;
    ++SpawnedThisRound;
    ++AliveCount;
    return true;
}
void ABlackPinesRoundDirector::RegisterZombieDeath()
{
    if(HasAuthority()) AliveCount=FMath::Max(0,AliveCount-1);
}
