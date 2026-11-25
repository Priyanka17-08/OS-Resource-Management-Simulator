import io
from pathlib import Path
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from modules.cpu_scheduling import fcfs, sjf, round_robin, srtf, preemptive_priority
from modules.disk_scheduling import fcfs as disk_fcfs, sstf, scan, c_scan
from modules.deadlock import is_safe_state

st.set_page_config(page_title="Resource Management Lab", page_icon="◐", layout="wide")

# ──────────────────────────────────────────────────────────────
#  THEME — soft pastel, minimal. All styling lives in style.css
# ──────────────────────────────────────────────────────────────
PALETTE = ["#B7C9AE", "#D8D1E8", "#C5D6E5", "#E4D5C3", "#E8CFCF", "#CFE0D8", "#DCD6EE", "#D5E2EC"]

st.markdown(f"<style>{(Path(__file__).parent / 'style.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def page_header(label, title, sub):
    st.markdown(
        f'<div class="page-head"><span class="crumb">{label}</span><h1>{title}</h1><p>{sub}</p></div>',
        unsafe_allow_html=True,
    )

def color_for(pid, order):
    if pid not in order:
        order.append(pid)
    return PALETTE[order.index(pid) % len(PALETTE)]

def style_axes(fig, ax):
    fig.patch.set_alpha(0)
    ax.set_facecolor("#FFFFFF")
    for s in ax.spines.values():
        s.set_color("#E8E6E1")
    ax.tick_params(colors="#6B6B68", labelsize=9)
    ax.xaxis.label.set_color("#6B6B68")
    ax.yaxis.label.set_color("#6B6B68")
    ax.grid(alpha=.6, color="#EFEDE8")
    ax.set_axisbelow(True)


# ──────────────────────────────────────────────────────────────
#  Sidebar
# ──────────────────────────────────────────────────────────────
st.sidebar.markdown(
    '<div class="brand"><span class="dot"></span>Resource Lab</div>'
    '<div class="brand-sub">Operating systems simulator</div>',
    unsafe_allow_html=True,
)
page = st.sidebar.radio("Navigate", ["Overview", "CPU Scheduling", "Memory Management", "Deadlock & Banker’s", "Disk Scheduling"])
st.sidebar.markdown("---")
st.sidebar.caption("Python · Streamlit")


def sample_processes():
    return [
        {"pid": "P1", "arrival": 0, "burst": 5, "priority": 3},
        {"pid": "P2", "arrival": 1, "burst": 4, "priority": 1},
        {"pid": "P3", "arrival": 2, "burst": 2, "priority": 4},
        {"pid": "P4", "arrival": 4, "burst": 6, "priority": 2},
        {"pid": "P5", "arrival": 6, "burst": 3, "priority": 5},
    ]

def memory_allocate(blocks, processes, strategy):
    remaining = blocks.copy()
    rows = []
    for i, size in enumerate(processes):
        candidates = [j for j, b in enumerate(remaining) if b >= size]
        chosen = None
        if candidates:
            if strategy == "First Fit": chosen = candidates[0]
            elif strategy == "Best Fit": chosen = min(candidates, key=lambda j: remaining[j])
            else: chosen = max(candidates, key=lambda j: remaining[j])
            remaining[chosen] -= size
        rows.append({"Process": f"P{i+1}", "Size": size, "Block": f"B{chosen+1}" if chosen is not None else "—", "Status": "Allocated" if chosen is not None else "Not allocated"})
    return pd.DataFrame(rows), remaining


# ──────────────────────────────────────────────────────────────
#  Pages
# ──────────────────────────────────────────────────────────────
if page == "Overview":
    st.markdown("""
<div class="page-head">
<h1>Resource Management Lab</h1>
<p>Explore how an operating system schedules the CPU, allocates memory, avoids deadlock and moves the disk head.</p>
</div>
""", unsafe_allow_html=True)

    mods = [
        ("CPU", "CPU Scheduling", "FCFS, SJF, Round Robin, SRTF and Priority with a Gantt chart.", "5 algorithms", "#E6EDE2"),
        ("Memory", "Memory Management", "First, Best and Worst Fit allocation with a block map.", "3 strategies", "#EEEAF5"),
        ("Deadlock", "Deadlock & Banker’s Algorithm", "Safe-state analysis, need matrix and safe sequence.", "2 tools", "#E6EEF5"),
        ("Disk", "Disk Scheduling", "FCFS, SSTF, SCAN and C-SCAN head movement.", "4 algorithms", "#EFE9DD"),
    ]
    cards = "".join(
        f'<div class="mcard"><span class="label" style="--bg-c:{c}">{lab}</span><h3>{t}</h3><p>{d}</p><div class="meta">{meta}</div></div>'
        for lab, t, d, meta, c in mods
    )
    st.markdown(f'<div class="cards">{cards}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CPU algorithms", "5")
    c2.metric("Memory strategies", "3")
    c3.metric("Deadlock tools", "2")
    c4.metric("Disk algorithms", "4")

    st.markdown("#### What each module does")
    st.dataframe(pd.DataFrame([
        {"Module": "CPU", "Purpose": "Calculate waiting and turnaround time"},
        {"Module": "Memory", "Purpose": "Allocate processes to available blocks"},
        {"Module": "Deadlock", "Purpose": "Check safe state and safe sequence"},
        {"Module": "Disk", "Purpose": "Calculate disk-head movement"},
    ]), use_container_width=True, hide_index=True)
    st.info("Choose a module from the sidebar to run a simulation. All values are editable samples.")

elif page == "CPU Scheduling":
    page_header("Module 1", "CPU Scheduling", "Choose an algorithm, edit the process table and run the simulation.")
    algo = st.selectbox("Algorithm", ["FCFS", "SJF (Non-preemptive)", "Round Robin", "SRTF", "Preemptive Priority"])
    default = pd.DataFrame(sample_processes())
    edited = st.data_editor(default, num_rows="dynamic", use_container_width=True, key="cpu_editor")
    quantum = st.number_input("Round Robin time quantum", min_value=1, value=2) if algo == "Round Robin" else 2
    if st.button("Run simulation", type="primary"):
        try:
            procs = []
            for _, r in edited.iterrows():
                procs.append({"pid": str(r["pid"]), "arrival": int(r["arrival"]), "burst": int(r["burst"]), "priority": int(r["priority"])})
            if not procs or any(p["arrival"] < 0 or p["burst"] <= 0 for p in procs): raise ValueError("Arrival must be ≥ 0 and burst must be > 0.")
            funcs = {"FCFS": fcfs, "SJF (Non-preemptive)": sjf, "Round Robin": lambda p: round_robin(p, quantum), "SRTF": srtf, "Preemptive Priority": preemptive_priority}
            results, gantt = funcs[algo](procs)
            df = pd.DataFrame(results)
            a, b = st.columns(2)
            a.metric("Average waiting time", f'{df["waiting"].mean():.2f}')
            b.metric("Average turnaround time", f'{df["turnaround"].mean():.2f}')

            st.markdown("#### Gantt chart")
            order = []
            total = max(e for _, _, e in gantt) - min(s for _, s, _ in gantt)
            blocks = ""
            for i, (pid, start, end) in enumerate(gantt):
                w = max((end - start) / total * 100, 2)
                end_lbl = f'<small class="end">{end}</small>' if i == len(gantt) - 1 else ""
                blocks += f'<div class="gb" style="--c:{color_for(pid, order)};flex:{w} 1 0">{pid}<small>{start}</small>{end_lbl}</div>'
            st.markdown(f'<div class="gantt">{blocks}</div>', unsafe_allow_html=True)

            st.markdown("#### Process results")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download results CSV", df.to_csv(index=False), "cpu_results.csv", "text/csv")
        except Exception as e:
            st.error(f"Could not run simulation: {e}")

elif page == "Memory Management":
    page_header("Module 2", "Memory Management", "Place processes into memory blocks and compare allocation strategies.")
    c1, c2 = st.columns(2)
    with c1: blocks_text = st.text_input("Memory block sizes (comma-separated)", "100, 500, 200, 300, 600")
    with c2: processes_text = st.text_input("Process sizes (comma-separated)", "212, 417, 112, 426")
    strategy = st.selectbox("Allocation strategy", ["First Fit", "Best Fit", "Worst Fit"])
    if st.button("Allocate memory", type="primary"):
        try:
            blocks = [int(x.strip()) for x in blocks_text.split(",") if x.strip()]
            processes = [int(x.strip()) for x in processes_text.split(",") if x.strip()]
            if not blocks or not processes or min(blocks + processes) <= 0: raise ValueError("Enter positive block and process sizes.")
            df, remaining = memory_allocate(blocks, processes, strategy)
            x, y, z = st.columns(3)
            x.metric("Allocated", f'{(df["Status"] == "Allocated").sum()} / {len(processes)}')
            y.metric("Not allocated", int((df["Status"] != "Allocated").sum()))
            z.metric("Remaining memory", sum(remaining))

            st.markdown("#### Block map")
            biggest = max(blocks)
            rows = ""
            for i, (orig, rem) in enumerate(zip(blocks, remaining)):
                used = orig - rem
                bar_w = orig / biggest * 100
                fill_w = used / orig * 100 if orig else 0
                label = f"{used} used" if used else ""
                rows += (
                    f'<div class="mem"><div class="nm">B{i+1}</div>'
                    f'<div class="bar" style="width:{bar_w}%;flex:none"><div class="fill" style="width:{fill_w}%">{label}</div></div>'
                    f'<div class="rem">{rem} free / {orig}</div></div>'
                )
            st.markdown(rows, unsafe_allow_html=True)

            st.markdown("#### Allocation table")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.download_button("Download allocation CSV", df.to_csv(index=False), "memory_allocation.csv", "text/csv")
        except Exception as e:
            st.error(f"Input error: {e}")

elif page == "Deadlock & Banker’s":
    page_header("Module 3", "Deadlock & Banker’s Algorithm", "Check whether the system is in a safe state and find a safe sequence.")
    allocation = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
    maximum = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
    available = [3, 3, 2]
    safe, sequence, need = is_safe_state(available, allocation, maximum)
    a, b = st.columns(2)
    a.metric("Available resources", str(available))
    b.metric("System state", "SAFE" if safe else "UNSAFE")

    st.markdown("#### Need matrix (Maximum − Allocation)")
    st.dataframe(pd.DataFrame(need, index=[f"P{i}" for i in range(len(need))], columns=["Resource A", "Resource B", "Resource C"]), use_container_width=True)

    if safe:
        st.markdown("#### Safe sequence")
        parts = []
        for i, p in enumerate(sequence):
            parts.append(f'<span class="chip" style="--c:{PALETTE[i % len(PALETTE)]}">{p}</span>')
        st.markdown('<div class="chips">' + '<span class="arrow">→</span>'.join(parts) + '</div>', unsafe_allow_html=True)
    else:
        st.error("No complete safe sequence found.")
    st.caption("A safe state means processes can finish in an order that releases resources for the remaining processes.")

elif page == "Disk Scheduling":
    page_header("Module 4", "Disk Scheduling", "Trace the read/write head and compare total head movement.")
    c1, c2, c3 = st.columns(3)
    with c1: req_text = st.text_input("Disk requests", "98, 183, 37, 122, 14, 124, 65, 67")
    with c2: head = st.number_input("Initial head position", min_value=0, max_value=9999, value=53)
    with c3: disk_size = st.number_input("Disk size (cylinders)", min_value=2, max_value=10000, value=200)
    algo = st.selectbox("Algorithm", ["FCFS", "SSTF", "SCAN", "C-SCAN"])
    direction = st.selectbox("Direction (SCAN/C-SCAN)", ["left", "right"], index=1)
    if st.button("Run simulation", type="primary"):
        try:
            requests = [int(x.strip()) for x in req_text.split(",") if x.strip()]
            if not requests: raise ValueError("Enter at least one request.")
            if head >= disk_size or any(r < 0 or r >= disk_size for r in requests): raise ValueError("Head and requests must be within 0 to disk size − 1.")
            if algo == "FCFS": order, movement, path = disk_fcfs(requests, int(head))
            elif algo == "SSTF": order, movement, path = sstf(requests, int(head))
            elif algo == "SCAN": order, movement, path = scan(requests, int(head), int(disk_size), direction)
            else: order, movement, path = c_scan(requests, int(head), int(disk_size), direction)
            a, b = st.columns(2)
            a.metric("Total head movement", f"{movement} cyl")
            b.metric("Requests serviced", len(order))

            st.markdown('<div class="lbl">Service order</div>', unsafe_allow_html=True)
            chips = '<span class="arrow">→</span>'.join(
                f'<span class="chip" style="--c:{PALETTE[i % len(PALETTE)]}">{r}</span>' for i, r in enumerate(order))
            st.markdown(f'<div class="chips">{chips}</div>', unsafe_allow_html=True)

            st.markdown("#### Head path")
            fig, ax = plt.subplots(figsize=(10, 3.6))
            style_axes(fig, ax)
            ax.plot(range(len(path)), path, color="#7F9DB9", linewidth=2, marker="o", markersize=7, markerfacecolor="#FFFFFF", markeredgewidth=2, markeredgecolor="#7F9DB9")
            ax.set_xlabel("Step"); ax.set_ylabel("Cylinder")
            fig.tight_layout()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", transparent=True, dpi=200, bbox_inches="tight")
            st.image(buf)
            st.download_button("Download disk path CSV", pd.DataFrame({"Step": range(len(path)), "Cylinder": path}).to_csv(index=False), "disk_path.csv", "text/csv")
        except Exception as e:
            st.error(f"Input error: {e}")

st.markdown('<div class="foot">Resource Management Lab · OS Simulator</div>', unsafe_allow_html=True)
