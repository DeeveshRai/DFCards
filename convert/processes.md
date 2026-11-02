{
  "id": "processes-and-threads",
  "name": "Processes and Threads",
  "cards": [
    {
      "id": "root",
      "parent_id": null,
      "question": "What are the main concepts involved in processes and threads?",
      "answer": "Process identity and state, execution and lifecycle, threads, workloads, and inter-process communication.",
      "order": 0
    },
    {
      "id": "fund",
      "parent_id": "root",
      "question": "What defines a process in an operating system?",
      "answer": "A running program instance with its own virtual address space, resources and execution state.",
      "order": 0
    },
    {
      "id": "program",
      "parent_id": "fund",
      "question": "How does a program differ from a process?",
      "answer": "A program is stored executable code; a process is an executing instance of it.",
      "order": 0
    },
    {
      "id": "ids",
      "parent_id": "fund",
      "question": "How are processes identified and related?",
      "answer": "A PID identifies a process; a PPID identifies its parent process.",
      "order": 1
    },
    {
      "id": "pid",
      "parent_id": "ids",
      "question": "What are PID and PPID?",
      "answer": "PID is a process identifier; PPID is its parent process identifier.",
      "order": 0
    },
    {
      "id": "pcb",
      "parent_id": "fund",
      "question": "What is a Process Control Block (PCB)?",
      "answer": "An OS data structure holding process metadata and execution context, such as state, registers, scheduling and resource information.",
      "order": 2
    },
    {
      "id": "states",
      "parent_id": "fund",
      "question": "What are the five common process states?",
      "answer": "New, ready, running, blocked/waiting, and terminated.",
      "order": 3
    },
    {
      "id": "new",
      "parent_id": "states",
      "question": "What does the new state mean?",
      "answer": "The process is being created and initialised.",
      "order": 0
    },
    {
      "id": "ready",
      "parent_id": "states",
      "question": "What does the ready state mean?",
      "answer": "The process can run but is waiting for CPU time.",
      "order": 1
    },
    {
      "id": "running",
      "parent_id": "states",
      "question": "What does the running state mean?",
      "answer": "The process is currently executing on a CPU.",
      "order": 2
    },
    {
      "id": "blocked",
      "parent_id": "states",
      "question": "What does the blocked/waiting state mean?",
      "answer": "The process cannot proceed until an event occurs, such as I/O completion.",
      "order": 3
    },
    {
      "id": "terminated",
      "parent_id": "states",
      "question": "What does the terminated state mean?",
      "answer": "The process has finished execution; its remaining OS bookkeeping may still need cleanup.",
      "order": 4
    },
    {
      "id": "execution",
      "parent_id": "root",
      "question": "How does the OS control process execution?",
      "answer": "Through scheduling, context switches, CPU privilege modes and system calls.",
      "order": 1
    },
    {
      "id": "switch",
      "parent_id": "execution",
      "question": "What is a context switch?",
      "answer": "The OS saves one execution context and restores another so the CPU can run a different thread or process.",
      "order": 0
    },
    {
      "id": "switchcost",
      "parent_id": "switch",
      "question": "Why do context switches have overhead?",
      "answer": "Saving/restoring state and disturbing caches or address-translation state consumes time without advancing application work.",
      "order": 0
    },
    {
      "id": "modes",
      "parent_id": "execution",
      "question": "How do user mode and kernel mode differ?",
      "answer": "User mode restricts privileged operations; kernel mode permits OS code to access protected resources.",
      "order": 1
    },
    {
      "id": "syscall",
      "parent_id": "modes",
      "question": "What is a system call?",
      "answer": "A controlled request from a user-space program for an operating-system service, typically entering kernel mode.",
      "order": 0
    },
    {
      "id": "lifecycle",
      "parent_id": "root",
      "question": "How are processes created, replaced and reaped on Unix-like systems?",
      "answer": "Commonly using fork() to create, exec() to replace a program, and wait() to collect child status.",
      "order": 2
    },
    {
      "id": "fork",
      "parent_id": "lifecycle",
      "question": "What does fork() do?",
      "answer": "Creates a child process, initially based on the parent; it returns different values in parent and child.",
      "order": 0
    },
    {
      "id": "forkreturn",
      "parent_id": "fork",
      "question": "What does fork() return?",
      "answer": "0 in the child; the child PID in the parent; -1 on failure.",
      "order": 0
    },
    {
      "id": "exec",
      "parent_id": "lifecycle",
      "question": "What does exec() do?",
      "answer": "Replaces the calling process image with a new program; on success it does not return.",
      "order": 1
    },
    {
      "id": "forkexec",
      "parent_id": "exec",
      "question": "How do fork() and exec() work together?",
      "answer": "A parent forks a child; the child can then exec a different program while retaining its process identity.",
      "order": 0
    },
    {
      "id": "wait",
      "parent_id": "lifecycle",
      "question": "What does wait() do?",
      "answer": "Lets a parent collect a terminated child’s exit status, blocking if no eligible child has exited yet.",
      "order": 2
    },
    {
      "id": "zombie",
      "parent_id": "wait",
      "question": "What is a zombie process?",
      "answer": "A terminated child whose exit status has not yet been collected by its parent.",
      "order": 0
    },
    {
      "id": "orphan",
      "parent_id": "lifecycle",
      "question": "What is an orphan process?",
      "answer": "A child whose parent has exited; it is reparented to an appropriate system process or subreaper.",
      "order": 3
    },
    {
      "id": "zvorph",
      "parent_id": "orphan",
      "question": "How do zombie and orphan processes differ?",
      "answer": "A zombie has terminated but awaits reaping; an orphan may still be running after its parent exits.",
      "order": 0
    },
    {
      "id": "daemon",
      "parent_id": "lifecycle",
      "question": "What is a daemon?",
      "answer": "A background service process, typically running without direct interactive terminal control.",
      "order": 4
    },
    {
      "id": "threads",
      "parent_id": "root",
      "question": "What is a thread, and how is it different from a process?",
      "answer": "A thread is an execution path within a process; threads share process resources but retain their own execution state.",
      "order": 3
    },
    {
      "id": "shared",
      "parent_id": "threads",
      "question": "What do threads of the same process share?",
      "answer": "The virtual address space, code, heap, global variables and process-level resources such as open file descriptors.",
      "order": 0
    },
    {
      "id": "private",
      "parent_id": "threads",
      "question": "What execution state is separate for each thread?",
      "answer": "Its stack, CPU registers, program counter and thread-specific scheduling state.",
      "order": 1
    },
    {
      "id": "tls",
      "parent_id": "private",
      "question": "What is thread-local storage (TLS)?",
      "answer": "Per-thread storage for variables so each thread gets its own instance rather than sharing one value.",
      "order": 0
    },
    {
      "id": "threadrisk",
      "parent_id": "shared",
      "question": "Why can shared memory between threads cause problems?",
      "answer": "Unsynchronised concurrent access can cause data races and inconsistent results.",
      "order": 0
    },
    {
      "id": "workload",
      "parent_id": "root",
      "question": "How do CPU-bound and I/O-bound processes differ?",
      "answer": "CPU-bound work spends most time computing; I/O-bound work often waits for input/output operations.",
      "order": 4
    },
    {
      "id": "cpu",
      "parent_id": "workload",
      "question": "What characterises a CPU-bound process?",
      "answer": "Performance is mainly limited by available CPU processing time.",
      "order": 0
    },
    {
      "id": "io",
      "parent_id": "workload",
      "question": "What characterises an I/O-bound process?",
      "answer": "Performance is mainly limited by I/O latency or throughput, with frequent waiting.",
      "order": 1
    },
    {
      "id": "ipc",
      "parent_id": "root",
      "question": "What is inter-process communication (IPC)?",
      "answer": "Mechanisms that let separate processes exchange data or coordinate actions.",
      "order": 5
    },
    {
      "id": "pipes",
      "parent_id": "ipc",
      "question": "What is an unnamed pipe?",
      "answer": "A unidirectional byte stream between file descriptors, commonly used by related processes.",
      "order": 0
    },
    {
      "id": "fifo",
      "parent_id": "ipc",
      "question": "What is a named pipe (FIFO)?",
      "answer": "A pipe exposed through a filesystem path so processes can open it independently.",
      "order": 1
    },
    {
      "id": "pipevsfifo",
      "parent_id": "fifo",
      "question": "How does a FIFO differ from an unnamed pipe?",
      "answer": "A FIFO has a filesystem name; an unnamed pipe is usually passed through inherited or shared file descriptors.",
      "order": 0
    },
    {
      "id": "shm",
      "parent_id": "ipc",
      "question": "What is shared memory IPC?",
      "answer": "Multiple processes map a common memory region for fast data exchange; synchronisation is usually required.",
      "order": 2
    },
    {
      "id": "mq",
      "parent_id": "ipc",
      "question": "What is a message queue?",
      "answer": "An OS-supported channel for sending and receiving discrete messages between processes.",
      "order": 3
    },
    {
      "id": "signals",
      "parent_id": "ipc",
      "question": "What is a signal in Unix-like systems?",
      "answer": "An asynchronous notification delivered to a process or thread to report an event or request action.",
      "order": 4
    },
    {
      "id": "sockets",
      "parent_id": "ipc",
      "question": "What is a socket?",
      "answer": "An endpoint for bidirectional communication, locally or across a network.",
      "order": 5
    },
    {
      "id": "choice",
      "parent_id": "shm",
      "question": "When would shared memory be preferable to message passing?",
      "answer": "For large or frequent data transfers when processes can coordinate safe access to a shared region.",
      "order": 0
    }
  ]
}