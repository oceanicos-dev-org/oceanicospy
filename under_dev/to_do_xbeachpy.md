# Boundary conditions

- The first three points are not considered in the writing of the boun conds because it was already known that they were not necessary but this can silently goes wrong for other applications
- what with the other methods such as the params and jonswap from swan?
- this line needs to be watched: def_write_sp2_header(self, forigin, fdest, lon, lat):
- this floc.write(f"0 {-(idx_site)*100} 'bounds_conds/filelist_{idx_site}.txt'\n") has a harcoded thing in terms of the negative sign there.
- 127 line the for loop for the header is too short
