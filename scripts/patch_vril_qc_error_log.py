#!/usr/bin/env python3
"""Temporary Android diagnostic: surface QuakeC PR_RunError details in logcat."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
path = root / "source/qcvm/pr_exec.c"
text = path.read_text(encoding="utf-8")

inc_anchor = '#include "pr_vm.h"\n'
inc = '''#include "pr_vm.h"
#if defined(__ANDROID__)
#include <android/log.h>
#endif
'''
if '<android/log.h>' not in text:
    if inc_anchor not in text:
        raise SystemExit("Could not find pr_exec include anchor")
    text = text.replace(inc_anchor, inc, 1)

anchor = '''\tPR_PrintStatement (pr_statements + pr_xstatement);
\tPR_StackTrace ();
\tCon_Printf ("%s\\n", string);

\tpr_depth = 0;'''
replacement = '''\tPR_PrintStatement (pr_statements + pr_xstatement);
\tPR_StackTrace ();
\tCon_Printf ("%s\\n", string);

#if defined(__ANDROID__)
\t__android_log_print(ANDROID_LOG_ERROR, "XZIEL_QC",
\t\t"PR_RunError: %s | statement=%d | function=%s | depth=%d",
\t\tstring,
\t\tpr_xstatement,
\t\tpr_xfunction ? PR_GetString(pr_xfunction->s_name) : "<null>",
\t\tpr_depth);
\tfor (int xziel_i = pr_depth - 1; xziel_i >= 0; --xziel_i) {
\t\tdfunction_t *xziel_f = pr_stack[xziel_i].f;
\t\tif (xziel_f) {
\t\t\t__android_log_print(ANDROID_LOG_ERROR, "XZIEL_QC",
\t\t\t\t"stack[%d]=%s statement=%d",
\t\t\t\txziel_i,
\t\t\t\tPR_GetString(xziel_f->s_name),
\t\t\t\tpr_stack[xziel_i].s);
\t\t}
\t}
#endif

\tpr_depth = 0;'''
if 'PR_RunError: %s | statement=' not in text:
    if anchor not in text:
        raise SystemExit("Could not find PR_RunError body anchor")
    text = text.replace(anchor, replacement, 1)

path.write_text(text, encoding="utf-8")
print("Patched Vril PR_RunError diagnostics for Android logcat.")
