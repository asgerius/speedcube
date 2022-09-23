#include "cube.h"


// Maps as generated by cube_maps.py
const char cmaps[12][24] = {  // Corners
    {9, 11, 10, 0, 2, 1, 3, 5, 4, 6, 8, 7, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 17, 16, 18, 20, 19, 21, 23, 22, 12, 14, 13},
    {14, 13, 12, 3, 4, 5, 6, 7, 8, 2, 1, 0, 23, 22, 21, 15, 16, 17, 18, 19, 20, 11, 10, 9},
    {0, 1, 2, 8, 7, 6, 20, 19, 18, 9, 10, 11, 12, 13, 14, 5, 4, 3, 17, 16, 15, 21, 22, 23},
    {4, 3, 5, 16, 15, 17, 6, 7, 8, 9, 10, 11, 1, 0, 2, 13, 12, 14, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 10, 9, 11, 22, 21, 23, 12, 13, 14, 15, 16, 17, 7, 6, 8, 19, 18, 20},
    {3, 5, 4, 6, 8, 7, 9, 11, 10, 0, 2, 1, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 21, 23, 22, 12, 14, 13, 15, 17, 16, 18, 20, 19},
    {11, 10, 9, 3, 4, 5, 6, 7, 8, 23, 22, 21, 2, 1, 0, 15, 16, 17, 18, 19, 20, 14, 13, 12},
    {0, 1, 2, 17, 16, 15, 5, 4, 3, 9, 10, 11, 12, 13, 14, 20, 19, 18, 8, 7, 6, 21, 22, 23},
    {13, 12, 14, 1, 0, 2, 6, 7, 8, 9, 10, 11, 16, 15, 17, 4, 3, 5, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 19, 18, 20, 7, 6, 8, 12, 13, 14, 15, 16, 17, 22, 21, 23, 10, 9, 11}
};
const char smaps[12][24] = {  // Sides
    {6, 7, 0, 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23, 16, 17},
    {9, 8, 2, 3, 4, 5, 6, 7, 17, 16, 10, 11, 12, 13, 1, 0, 15, 14, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 13, 12, 6, 7, 8, 9, 5, 4, 21, 20, 14, 15, 16, 17, 18, 19, 11, 10, 22, 23},
    {0, 1, 10, 11, 4, 5, 6, 7, 2, 3, 18, 19, 12, 13, 14, 15, 16, 17, 8, 9, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 14, 15, 8, 9, 10, 11, 6, 7, 22, 23, 16, 17, 18, 19, 20, 21, 12, 13},
    {2, 3, 4, 5, 6, 7, 0, 1, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 22, 23, 16, 17, 18, 19, 20, 21},
    {15, 14, 2, 3, 4, 5, 6, 7, 1, 0, 10, 11, 12, 13, 17, 16, 9, 8, 18, 19, 20, 21, 22, 23},
    {0, 1, 2, 3, 11, 10, 6, 7, 8, 9, 21, 20, 5, 4, 14, 15, 16, 17, 18, 19, 13, 12, 22, 23},
    {0, 1, 8, 9, 4, 5, 6, 7, 18, 19, 2, 3, 12, 13, 14, 15, 16, 17, 10, 11, 20, 21, 22, 23},
    {0, 1, 2, 3, 4, 5, 12, 13, 8, 9, 10, 11, 22, 23, 6, 7, 16, 17, 18, 19, 20, 21, 14, 15}
};

void cube_act(face *state, action action) {

    // Slightly faster by only looking up maps once
    const char *restrict cmap = cmaps[action];
    const char *restrict smap = smaps[action];
    char j;
    // Map corners
    for (j = 0; j < 8; ++ j) {
        state[j] = cmap[state[j]];
    }
    // Map sides
    for (j = 8; j < 20; ++ j) {
        state[j] = smap[state[j]];
    }
}

void cube_multi_act(face *states, const action *actions, size_t n) {
    // Performs n actions on n states in-place
    #pragma omp parallel for
    for (size_t i = 0; i < n; ++ i) {
        // Row pointer for easy indexing
        face *restrict p_state = states + 20 * i;
        // Slightly faster by only looking up maps once
        const action action = actions[i];
        const char *restrict cmap = cmaps[action];
        const char *restrict smap = smaps[action];
        char j;
        // Map corners
        for (j = 0; j < 8; ++ j) {
            p_state[j] = cmap[p_state[j]];
        }
        // Map sides
        for (j = 8; j < 20; ++ j) {
            p_state[j] = smap[p_state[j]];
        }
    }
}
