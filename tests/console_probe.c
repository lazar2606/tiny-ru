/* Exercise the real DOS console path with BIOS keyboard input, not a file. */
#define main tiny_application_main
#include "../dos/TINY.C"
#undef main

int main(void)
{
    static const unsigned char word[] = {175,224,168,162,165,226,63,13};
    static char line[256], q[MAXQ+1];
    union REGS in, out;
    FILE *log;
    int i, status, length, ok;
    if (!isatty(0)) return 10;
    while (kbhit()) getch();
    for (i=0;i<8;i++) {
        memset(&in,0,sizeof(in));
        in.h.ah=5;
        in.h.cl=word[i];
        int86(0x16,&in,&out);
        if (out.h.al) return 11;
    }
    status=read_console_line(line,sizeof(line));
    length=clean(line,q);
    ok=status==1 && length==7 && !strcmp(q,"\257\340\250\242\245\342?");
    log=fopen("CONSOLE.LOG","wb");
    if (!log) return 12;
    fprintf(log,"tty=%d status=%d length=%d ok=%d\r\n",isatty(0),status,length,ok);
    fwrite(q,1,strlen(q),log);
    fclose(log);
    return ok ? 0 : 13;
}
