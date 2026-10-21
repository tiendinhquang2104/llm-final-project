#define _CRT_SECURE_NO_WARNINGS
#define N 10000000
#include <stdio.h>

void NhapMang(int a[], int n) {
	for (int i = 0; i < n; i++) {
		printf("a[%d] = ", i);
		scanf("%d", &a[i]);
	}
}

void LoaiBoPhanTuTrung(int a[], int n) {
	int cnt[N] = { 0 };
	for (int i = 0; i < n; i++) {
		cnt[a[i]]++;
		for (int i = 0; i < n; i++) {
			if (cnt[a[i]] != 0) {
				printf("%d", a[i]);
				cnt[a[i]] == 0;
			}
		}
	}

}

void XuatMang(int a[], int n) {
	for (int i = 0; i < n; i++) {
		printf("%d ", a[i]);
	}
}




int main() {
	int a[N], int n;
	do
	{
		printf("Moi thay nhap vao so luong phan tu : ");
		scanf("%d", &n);
	} while (n<1||n>10000);
	
	NhapMang(a, n);
	LoaiBoPhanTuTrung(a, n);
	XuatMang(a, n);

	return 0;
}