"""Code-defined LaTeX starter templates (Owner idea #24, parity slice 10).

A small curated gallery — pick one to seed a manuscript's main.tex. No DB table; the
templates live here so they version with the code.
"""

TEMPLATES = {
    "article": {
        "name": "Article",
        "description": "A clean single-column article with sections and a bibliography.",
        "body": r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{graphicx}
\usepackage{amsmath}

\title{Title}
\author{Author}
\date{\today}

\begin{document}
\maketitle

\begin{abstract}
A short abstract.
\end{abstract}

\section{Introduction}
Start here.

\section{Methods}

\section{Results}

\section{Discussion}

\bibliographystyle{plain}
\bibliography{references}
\end{document}
""",
    },
    "two-column": {
        "name": "Two-column",
        "description": "A two-column conference-style layout.",
        "body": r"""\documentclass[10pt,twocolumn]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage{amsmath}
\usepackage{graphicx}

\title{Title}
\author{Author}

\begin{document}
\maketitle

\begin{abstract}
A short abstract.
\end{abstract}

\section{Introduction}

\section{Method}

\section{Experiments}

\section{Conclusion}

\bibliographystyle{plain}
\bibliography{references}
\end{document}
""",
    },
    "ieee": {
        "name": "IEEE-style",
        "description": "Two-column technical paper in the IEEE house style.",
        "body": r"""\documentclass[conference]{IEEEtran}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}

\title{Title}
\author{\IEEEauthorblockN{Author}\IEEEauthorblockA{Affiliation}}

\begin{document}
\maketitle

\begin{abstract}
A short abstract.
\end{abstract}

\begin{IEEEkeywords}
keyword, keyword
\end{IEEEkeywords}

\section{Introduction}

\section{Related Work}

\section{Method}

\section{Results}

\section{Conclusion}

\bibliographystyle{IEEEtran}
\bibliography{references}
\end{document}
""",
    },
    "beamer": {
        "name": "Beamer slides",
        "description": "A presentation deck with title and content frames.",
        "body": r"""\documentclass{beamer}
\usetheme{default}
\usecolortheme{seabird}

\title{Title}
\author{Author}
\date{\today}

\begin{document}

\frame{\titlepage}

\begin{frame}{Outline}
\tableofcontents
\end{frame}

\section{Introduction}
\begin{frame}{Introduction}
\begin{itemize}
  \item First point
  \item Second point
\end{itemize}
\end{frame}

\section{Results}
\begin{frame}{Results}
Content.
\end{frame}

\end{document}
""",
    },
    "thesis-chapter": {
        "name": "Thesis chapter",
        "description": "A report-class chapter with sections, ready to \\include.",
        "body": r"""\documentclass[12pt]{report}
\usepackage[margin=1.25in]{geometry}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{setspace}
\onehalfspacing

\begin{document}

\chapter{Chapter Title}
\label{ch:one}

\section{Introduction}
Open the chapter.

\section{Background}

\section{Approach}

\section{Summary}

\end{document}
""",
    },
    "cover-letter": {
        "name": "Cover letter",
        "description": "A submission cover letter to an editor.",
        "body": r"""\documentclass[11pt]{letter}
\usepackage[margin=1in]{geometry}

\signature{Author}
\address{Affiliation \\ Address}

\begin{document}

\begin{letter}{Editor \\ Journal Name}
\opening{Dear Editor,}

We are pleased to submit our manuscript, ``Title'', for consideration.

\closing{Sincerely,}

\end{letter}
\end{document}
""",
    },
}


def template_choices():
    return [(key, t["name"]) for key, t in TEMPLATES.items()]


def template_body(key: str) -> str:
    return TEMPLATES.get(key, TEMPLATES["article"])["body"]
