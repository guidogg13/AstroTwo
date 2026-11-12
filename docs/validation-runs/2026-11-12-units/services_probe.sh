#!/bin/sh
date -u +"%Y-%m-%dT%H:%M:%SZ"
p() { printf "%-14s " "$1"; curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" --max-time 60 "$2" || echo "errore curl $?"; }
p SIMBAD-TAP "https://simbad.cds.unistra.fr/simbad/sim-tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&QUERY=SELECT%20TOP%201%20main_id%20FROM%20basic"
p Sesame "https://cds.unistra.fr/cgi-bin/nph-sesame/-oxp/SNV?Vega"
p TAPVizieR "https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&QUERY=SELECT%20TOP%201%20*%20FROM%20%22II/246/out%22"
p VizieR "https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=II/246"
p MocServer "https://alasky.cds.unistra.fr/MocServer/query?ID=CDS/P/DSS2/color&get=record"
p XMatch "https://cdsxmatch.cds.unistra.fr/xmatch/api/v1/sync/tables?action=getVizieRTableNames"
p Gaia-TAP "https://gea.esac.esa.int/tap-server/tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&QUERY=SELECT%20TOP%201%20source_id%20FROM%20gaiadr3.gaia_source"
p NASA-TAP "https://exoplanetarchive.ipac.caltech.edu/TAP/sync?query=select+top+1+pl_name+from+ps&format=votable"
p SIMBAD-Harv "https://simbad.harvard.edu/simbad/sim-tap/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&QUERY=SELECT%20TOP%201%20main_id%20FROM%20basic"
