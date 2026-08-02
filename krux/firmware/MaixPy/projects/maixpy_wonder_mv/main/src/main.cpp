#include "maixpy.h"
#include "sdcard.h"
void * __dso_handle = 0 ;
extern sdcard_config_t config;

int main()
{
    sdcard_config_t amigo = { 30, 31, 29, 32, SD_CS_PIN };
    config = amigo;
    maixpy_main();
    return 0;
}
