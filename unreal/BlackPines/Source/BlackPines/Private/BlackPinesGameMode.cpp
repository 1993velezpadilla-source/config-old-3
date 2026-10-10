#include "BlackPinesGameMode.h"
#include "BlackPinesCharacter.h"
ABlackPinesGameMode::ABlackPinesGameMode()
{
    DefaultPawnClass=ABlackPinesCharacter::StaticClass();
}
