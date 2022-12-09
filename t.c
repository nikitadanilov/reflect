#include <stdio.h>

static int x;
static const int y = 1;
struct SS {
	char t;
	char a[6];
};

struct SS ss;

int f(int **p) {
	char *wrong = (void *)&ss + 67;
	const char *null  = (void *)0;
	const char **nil = &null;
	printf("%p %p %i\n", p, *p, **p);
	if (--**p > 0) {
		f(p);
		printf("out: %p %p\n", wrong, nil);
	}
	return **p;
}

int main(int argc, char **argv) {
	int *p = &argc;
	printf("%p %p\n", p, &p);
	{
		int **pp = &p;
		f(pp);
		{
			int g[] = { 5, x, y, 2, 1 };
			int *gg = g;
			f(&gg);
			printf("%p %p\n", &g, argv);
		}
	}
	return 0;
}

int g(void) {
	static int GG = 3;
	return GG;
}
