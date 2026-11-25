/* Compile with GCC or Turbo C: self-contained tokenizer/context probe. */
#define main tiny_application_main
#include "../dos/TINY.C"
#undef main

int main(void)
{
    int i, n, skip_lf = 0;
    FILE *fp;
    char input[300], output[MAXQ+1];
    for (i=0;i<256;i++)
        if (ru_cp_to_id[i]>=VOCAB) return 1;
    for (i=2;i<VOCAB;i++)
        if (ru_cp_to_id[ru_id_to_cp[i]]!=i) return 2;
    /* CP866 uppercase YO (F0), lower YO (F1), Cyrillic A (80/A0). */
    input[0]=(char)0xf0; input[1]=(char)0xf1;
    input[2]=(char)0x80; input[3]=(char)0xa0; input[4]=0;
    n=clean(input,output);
    if (n!=4 || (unsigned char)output[0]!=0xf1 ||
        (unsigned char)output[1]!=0xf1 ||
        (unsigned char)output[2]!=0xa0 ||
        (unsigned char)output[3]!=0xa0) return 3;
    memset(input,'a',MAXQ); input[MAXQ]=0;
    if (clean(input,output)!=MAXQ) return 4;
    input[MAXQ]='a'; input[MAXQ+1]=0;
    if (clean(input,output)!=-1 || output[0]!=0) return 5;
    if (clean("",output)!=0) return 6;
    fp = tmpfile();
    if (!fp) return 7;
#ifdef RU_DOS_CONSOLE
    setmode(fileno(fp), O_BINARY);
#endif
    fputs("one\rtwo\r\nthree\nfour",fp);
    rewind(fp);
    if (read_plain_line(fp,input,sizeof(input),&skip_lf)!=1 || strcmp(input,"one")) return 8;
    if (read_plain_line(fp,input,sizeof(input),&skip_lf)!=1 || strcmp(input,"two")) return 9;
    if (read_plain_line(fp,input,sizeof(input),&skip_lf)!=1 || strcmp(input,"three")) return 10;
    if (read_plain_line(fp,input,sizeof(input),&skip_lf)!=1 || strcmp(input,"four")) return 11;
    if (read_plain_line(fp,input,sizeof(input),&skip_lf)!=0) return 12;
    fclose(fp);
    puts("CP866 and context checks passed");
    return 0;
}
