#include "BlackPinesRoundDirector.h"

#include "BlackPinesZombie.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"

ABlackPinesRoundDirector::ABlackPinesRoundDirector()
{
    PrimaryActorTick.bCanEverTick = false;
    bReplicates = true;
    ZombieClass = ABlackPinesZombie::StaticClass();
}

void ABlackPinesRoundDirector::BeginPlay()
{
    Super::BeginPlay();

    if (!HasAuthority())
    {
        return;
    }

    RefreshSpawnPoints();
    BeginNextRound();

    if (UWorld* World = GetWorld())
    {
        World->GetTimerManager().SetTimer(
            SpawnTimerHandle,
            this,
            &ABlackPinesRoundDirector::SpawnTick,
            FMath::Max(0.10f, SpawnInterval),
            true,
            0.25f);
    }
}

int32 ABlackPinesRoundDirector::WavePopulation(int32 Wave, int32 Players) const
{
    const int32 W = FMath::Max(1, Wave);
    const int32 P = FMath::Clamp(Players, 1, 4);
    const int32 Cap = FMath::Max(24, MaxSoloWave) + (P - 1) * 16;

    if (W >= 100)
    {
        return Cap;
    }

    if (W < 10)
    {
        return 6 + (W - 1) * 3 + (P - 1) * 3;
    }

    const float Mult = P == 1 ? 3.f : static_cast<float>(P - 1) * 6.f;
    return FMath::Clamp(
        FMath::FloorToInt(24.f + Mult * W * W * .03f),
        1,
        Cap);
}

int32 ABlackPinesRoundDirector::ZombieHealth(int32 Wave) const
{
    const int32 W = FMath::Max(1, Wave);

    if (W <= 9)
    {
        return W * 100 + 50;
    }

    if (W >= 90)
    {
        return FMath::Max(950, MaxHealth);
    }

    return FMath::Min(
        FMath::Max(950, MaxHealth),
        FMath::FloorToInt(950.f * FMath::Pow(1.1f, static_cast<float>(W - 9))));
}

bool ABlackPinesRoundDirector::BeginNextRound()
{
    if (!HasAuthority() ||
        AliveCount != 0 ||
        SpawnedThisRound < RoundTotal ||
        CurrentRound == MAX_int32)
    {
        return false;
    }

    int32 ConnectedPlayers = 0;
    if (const UWorld* World = GetWorld())
    {
        for (FConstPlayerControllerIterator It = World->GetPlayerControllerIterator(); It; ++It)
        {
            if (It->Get())
            {
                ++ConnectedPlayers;
            }
        }
    }

    PlayerCount = FMath::Clamp(
        ConnectedPlayers > 0 ? ConnectedPlayers : PlayerCount,
        1,
        4);

    ++CurrentRound;
    RoundTotal = WavePopulation(CurrentRound, PlayerCount);
    SpawnedThisRound = 0;
    AliveCount = 0;
    return true;
}

bool ABlackPinesRoundDirector::RegisterZombieSpawn()
{
    if (!HasAuthority() ||
        SpawnedThisRound >= RoundTotal ||
        AliveCount >= FMath::Max(1, MaxAlive))
    {
        return false;
    }

    ++SpawnedThisRound;
    ++AliveCount;
    return true;
}

void ABlackPinesRoundDirector::RegisterZombieDeath()
{
    if (HasAuthority())
    {
        AliveCount = FMath::Max(0, AliveCount - 1);
    }
}

void ABlackPinesRoundDirector::RefreshSpawnPoints()
{
    SpawnPoints.Reset();

    if (!GetWorld())
    {
        return;
    }

    TArray<AActor*> Found;
    UGameplayStatics::GetAllActorsWithTag(GetWorld(), SpawnPointTag, Found);

    SpawnPoints.Reserve(Found.Num());
    for (AActor* Actor : Found)
    {
        if (IsValid(Actor) && Actor != this)
        {
            SpawnPoints.Add(Actor);
        }
    }

    SpawnCursor = 0;
}

bool ABlackPinesRoundDirector::SpawnOneZombie()
{
    if (!HasAuthority() ||
        !ZombieClass ||
        SpawnedThisRound >= RoundTotal ||
        AliveCount >= FMath::Max(1, MaxAlive))
    {
        return false;
    }

    if (SpawnPoints.IsEmpty())
    {
        RefreshSpawnPoints();
    }

    if (SpawnPoints.IsEmpty())
    {
        return false;
    }

    AActor* SpawnPoint = SpawnPoints[SpawnCursor % SpawnPoints.Num()];
    ++SpawnCursor;

    if (!IsValid(SpawnPoint))
    {
        RefreshSpawnPoints();
        return false;
    }

    FActorSpawnParameters Params;
    Params.SpawnCollisionHandlingOverride =
        ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

    ABlackPinesZombie* Zombie = GetWorld()->SpawnActor<ABlackPinesZombie>(
        ZombieClass,
        SpawnPoint->GetActorTransform(),
        Params);

    if (!Zombie)
    {
        return false;
    }

    if (!RegisterZombieSpawn())
    {
        Zombie->Destroy();
        return false;
    }

    Zombie->InitializeForRound(CurrentRound, this);
    return true;
}

void ABlackPinesRoundDirector::SpawnTick()
{
    if (!HasAuthority())
    {
        return;
    }

    if (SpawnedThisRound < RoundTotal)
    {
        SpawnOneZombie();
        return;
    }

    if (AliveCount == 0 && GetWorld())
    {
        FTimerManager& TimerManager = GetWorld()->GetTimerManager();
        if (!TimerManager.IsTimerActive(NextRoundTimerHandle))
        {
            TimerManager.SetTimer(
                NextRoundTimerHandle,
                this,
                &ABlackPinesRoundDirector::BeginNextRoundAfterDelay,
                FMath::Max(0.f, InterRoundDelay),
                false);
        }
    }
}

void ABlackPinesRoundDirector::BeginNextRoundAfterDelay()
{
    BeginNextRound();
}
