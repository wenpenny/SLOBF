/* SLOBF obfuscator test functions.
   Each function is designed to exercise specific operators.
   Functions are sized appropriately for their target operator thresholds. */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- OPI target: statements to wrap (not just declarations) ---- */
int opi_add(int a, int b) {
    int c = a + b;
    int d = c * 2;
    int e = d - a;
    c = c + 1;
    d = d - 1;
    e = e * 2;
    return e;
}

/* ---- CFF target: >= 5 statements with if-else ---- */
int cff_classify(int x, int y) {
    int result = 0;
    int tmp = x + y;
    int diff = x - y;
    if (x > 10) {
        result = x * y;
        result = result + tmp;
    } else {
        result = x + y;
        result = result - diff;
    }
    result = result + 1;
    return result;
}

/* ---- CFF target: >= 5 statements with loop ---- */
int cff_sum_range(int start, int end) {
    int s = 0;
    int i = start;
    int n = end - start + 1;
    int step = 1;
    for (i = start; i <= end; i++) {
        s += i;
    }
    s = s + n - step;
    return s;
}

/* ---- CFF edge case: loop with break (should be rejected) ---- */
int cff_find_positive(int *arr, int n) {
    int i;
    for (i = 0; i < n; i++) {
        if (arr[i] > 0) break;
    }
    return i;
}

/* ---- CFF edge case: loop with continue (should be rejected) ---- */
int cff_count_even(int *arr, int n) {
    int count = 0;
    int i;
    for (i = 0; i < n; i++) {
        if (arr[i] % 2 != 0) continue;
        count++;
    }
    return count;
}

/* ---- ER target: functions with various expressions ---- */
int er_arithmetic(int x, int y) {
    int a = x + y;
    int b = x - y;
    int c = x * 2;
    int d = x & y;
    int e = x | y;
    int f = x ^ y;
    return a + b + c + d + e + f;
}

int er_logical(int x, int y) {
    if ((x > 0) && (y > 0)) return 1;
    if ((x > 0) || (y > 0)) return 2;
    return 0;
}

int er_pre_inc(int x) {
    int y = ++x;
    int z = --x;
    return y + z;
}

/* ---- DE target: functions with constants and string literals ---- */
int de_constants(int x) {
    int a = x * 42;
    int b = a + 100;
    int c = b / 256;
    int d = c * 3;
    return c + d;
}

const char* de_message(int code) {
    int t = code + 1;
    if (t == 1) return "success";
    if (t == 2) return "not_found";
    t = code * 2;
    return "unknown_err";
}

/* ---- JCI target: >= 2 statements ---- */
int jci_process(int a, int b, int c) {
    int x = a + b;
    int y = b * c;
    int z = x - y;
    int w = z + 1;
    int u = w * 2;
    return u;
}

/* ---- FS target: >= 8 statements, suitable for splitting ---- */
int fs_long_compute(int x, int y, int z) {
    int a = x + y;
    int b = y * z;
    int c = a - b;
    int d = c * 2;
    int e = d + x;
    int f = e * y;
    int g = f - z;
    int h = g + a;
    int result = h + x + y + z;
    return result;
}

/* ---- FS target: >= 8 statements with float type parameter ---- */
float fs_float_op(int x, float factor) {
    float a = (float)x * factor;
    float b = a + 1.5f;
    float c = b * 2.0f;
    float d = c - 1.0f;
    float e = d * factor;
    float f = e + 3.0f;
    float g = f / 2.0f;
    float h = g * factor;
    return c + d + e + f + g + h;
}

/* ---- FS edge case: multiple returns (should be rejected) ---- */
int fs_multi_return(int x) {
    if (x > 0) return 1;
    if (x < 0) return -1;
    return 0;
}

/* ---- Compound test: all operators should preserve semantics ---- */
int compound_basic(int n) {
    int a = n + 7;
    int b = a * 13;
    int c = b - 5;
    int d = c / 3;
    return d;
}

/* ---- Main: run all tests ---- */
int main(int argc, char **argv) {
    int failures = 0;

    if (opi_add(3, 4) != 22) { printf("FAIL: opi_add\n"); failures++; }

    if (cff_classify(5, 3) != 7)  { printf("FAIL: cff_classify(5,3)\n"); failures++; }
    if (cff_classify(15, 3) != 64) { printf("FAIL: cff_classify(15,3)\n"); failures++; }
    if (cff_sum_range(1, 5) != 19) { printf("FAIL: cff_sum_range\n"); failures++; }

    {
        int arr1[] = {0, 0, 5, 0};
        if (cff_find_positive(arr1, 4) != 2) { printf("FAIL: cff_find_positive\n"); failures++; }
    }
    {
        int arr2[] = {1, 2, 3, 4};
        if (cff_count_even(arr2, 4) != 2) { printf("FAIL: cff_count_even\n"); failures++; }
    }

    if (er_arithmetic(3, 5) != (3+5)+(3-5)+(3*2)+(3&5)+(3|5)+(3^5))
        { printf("FAIL: er_arithmetic\n"); failures++; }
    if (er_logical(1, 1) != 1) { printf("FAIL: er_logical(1,1)\n"); failures++; }
    if (er_logical(1, -1) != 2) { printf("FAIL: er_logical(1,-1)\n"); failures++; }
    if (er_logical(-1, -1) != 0) { printf("FAIL: er_logical(-1,-1)\n"); failures++; }
    {
        int x = 5;
        int r = er_pre_inc(x);
        if (r != 11) { printf("FAIL: er_pre_inc\n"); failures++; }
    }

    if (de_constants(3) != ((3*42 + 100) / 256) * 4) { printf("FAIL: de_constants\n"); failures++; }
    if (strcmp(de_message(0), "success") != 0) { printf("FAIL: de_message(0)\n"); failures++; }
    if (strcmp(de_message(2), "unknown_err") != 0) { printf("FAIL: de_message(2)\n"); failures++; }

    {
        int r = jci_process(2, 3, 4);
        if (r != ((2+3) - (3*4) + 1) * 2) { printf("FAIL: jci_process\n"); failures++; }
    }

    {
        int r = fs_long_compute(1, 2, 3);
        if (r != -4) { printf("FAIL: fs_long_compute got %d\n", r); failures++; }
    }
    {
        float r = fs_float_op(2, 1.5f);
        float expected = (3.0f+1.5f)*2.0f + 9.0f-1.0f + (9.0f-1.0f)*1.5f + (9.0f-1.0f)*1.5f+3.0f + ((9.0f-1.0f)*1.5f+3.0f)/2.0f + ((9.0f-1.0f)*1.5f+3.0f)/2.0f*1.5f;
        if (r != expected) { printf("FAIL: fs_float_op got %f expected %f\n", r, expected); failures++; }
    }

    if (fs_multi_return(5) != 1)  { printf("FAIL: fs_multi_return(5)\n"); failures++; }
    if (fs_multi_return(-5) != -1) { printf("FAIL: fs_multi_return(-5)\n"); failures++; }
    if (fs_multi_return(0) != 0)  { printf("FAIL: fs_multi_return(0)\n"); failures++; }

    {
        int r = compound_basic(2);
        if (r != ((2+7)*13 - 5) / 3) { printf("FAIL: compound_basic\n"); failures++; }
    }

    if (failures == 0) {
        printf("ALL TESTS PASSED\n");
    } else {
        printf("%d TESTS FAILED\n", failures);
    }
    return failures;
}
