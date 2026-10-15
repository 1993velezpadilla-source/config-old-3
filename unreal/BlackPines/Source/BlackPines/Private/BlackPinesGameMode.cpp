#include "BlackPinesGameMode.h"

#include "BlackPinesCharacter.h"
#include "BlackPinesRoundDirector.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"

ABlackPinesGameMode::ABlackPinesGameMode()
{
    DefaultPawnClass = ABlackPinesCharacter::StaticClass();
    RoundDirectorClass = ABlackPinesRoundDirector::StaticClass();
}

void ABlackPinesGameMode::StartPlay()
{
    Super::StartPlay();

    UWorld* World = GetWorld();
    if (!World || !RoundDirectorClass)
    {
        return;
    }

    if (!UGameplayStatics::GetActorOfClass(World, RoundDirectorClass))
    {
        World->SpawnActor<ABlackPinesRoundDirector>(
            RoundDirectorClass,
            FVector::ZeroVector,
            FRotator::ZeroRotator);
    }
}
