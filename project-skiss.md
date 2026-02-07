
## Definition of the project

### Motivation

You are working with Claude Code and you send it off on a 30-minute job. During that time, you want to go through other parts of the repo and potentially check, add, or refine things in other files.

A common problem is that one agent screws up the context for the other.

To avoid this, the agent you are using must know what the other one is doing.

Therefore, we will create a tool/function so that Claude can tell where it is and Gemini (for example) can check it out.

Ideas (prio 1 - 3, where 1 is most important)
To be able to save visited nodes, so that Gemini knows that Claude can have that specific file in its context even if it is not currently "working" there (prio 3)
Index the repo at a folder level: a folder is a node...


We start with one step.

Clients involved: Gem, Claude...

One MCP.

One KG.

After the free agent is done, it calls a re-indexer which re-indexes the repo...

### Presentation

Have about 5 folders, an app, a db, a ui or something, then let Claude go off on a work (a bit longer), and then claim 3 of the folders so it "holds them" and show that it is working on them. At that point, the UI should visualize this by lighting them up in orange or something... Then we should ask Gemini if it can change something in the database, and we say something like go in and change this, and should get back the answer "claude is currently working on this"...

### Parts

1 - Automatic indexer (create KG)

....

Output: indexed repo in a format that the MCP can read
Indexering på filnivå
Stretch indexering på funktion niv

Nodes:
Codebase
Repo
Directory
File
Agent
(Optional) Function

2 - MCP interaction with Knowledge graph
2.1 Create the MCP
2.2 Put together with the repo's indexing

### Tools:
Release and Reindex Nodes
Claim Node
Get_active_agents
query_codebase

The MCP is supposed to be accessed from both Claude and Gemini. It is supposed to provide tools for the agent to connect to the DB, which should include what nodes the other agent is currently working on. The agents should be instructed to use the tools after each file it brings into memory or is intended to edit. Basically claiming the nodes/files for the time it is working on/using them. After finishing it should call another function to release the claiming and it will reindex the codebase. 


### 3 - Visualization tool for demo
Draft for UI 
Use Streamlit app only. 
The UI should visualise the agents interaction with the codebase. When for example Claude looks at the folder App and is planning to edit the files within it, the node should light up. 


### Prework
Set up neo4j community instance - Tom
CLAUDE.md 
Skills.md file for claude - Simon









