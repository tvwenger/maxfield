# Ingress Maxfield (v4.0)
## An [Ingress](https://ingress.com/) Linking and Fielding Strategy Generator

![Maxfield Demonstration](https://raw.githubusercontent.com/tvwenger/maxfield/master/example/plan_movie.gif?s=200)

### Introduction

This is for Ingress. If you don't know what that is, you're lost.

Maxfield is a tool that generates a linking and fielding plan for a
group of portals and a group of cooperating agents. Maxfield attempts
to **maximize** AP, **minimize** the number of keys required for any
one portal, and **minimize** to total time required to complete the
fielding operation.

Although generating an ideal (i.e. max AP) fielding plan is [fairly
straightforward](https://www.youtube.com/watch?v=priezq6Dm4Y),
identifying the optimal order to create the links to minimize walking
is a [computationally challenging
problem](https://en.wikipedia.org/wiki/Computational_complexity_theory).
Maxfield simplifies the problem by *approximating* the ideal linking
order: it generates many possible solutions and picks the best.

Since Maxfield generates random, nearly-ideal linking plans, you will
likely get a new plan every time you run the tool. Each plan will
almost certainly have the maximum possible AP, but the linking order
and walking distance may be different.

This version (v4.0) is a nearly complete re-write of the original
Maxfield code (based originally off of work by J. Peter Baker), which
brings Maxfield into the future with Python 3, fixes many bugs, and
improves the algorithm dramatically. Previous users of Maxfield will
notice that plans are now much more efficient in that they require
fewer keys from any individual portal, and the link order is more
sensible for multi-agent operations.

You can download this tool and run it locally on your computer by
following the instructions below. Or, you can use the on-line version
of this tool: http://www.ingress-maxfield.com

### Installation

Maxfield is written in Python 3 and is easy to install assuming
you have a Python environment on your computer. The `pygifsicle`
package depends on `gifsicle`, so you will need to install `gifsicle`.
Instructions can be [found here](https://www.lcdf.org/gifsicle/).

Once that's done, installing Maxfield (tested on Linux) is as easy as:

	python setup.py install
	
Now you can run Maxfield using the command `maxfield-plan` at the
command line.

I am not too familiar with Python on Windows, but here is how I tested
an installation on Windows 10 in a virtual environment. I downloaded
this repository as a `.zip` and extracted the contents to 
`C:\Users\username\Documents\maxfield`

	cd C:\Users\username\Documents\maxfield
	"C:\Program Files\Python38\python.exe" -m venv env
	env\Scripts\activate
	pip install numpy networkx scipy ortools matplotlib imageio pygifsicle
	python setup.py install
	
Then, Maxfield can be launched on Windows from any folder via

	C:\Users\username\Documents\maxfield\env\Scripts\activate
	python C:\Users\username\Documents\maxfield\bin\maxfield-plan

N.B. There is a bug with the latest version of `ortools`, so we use
an older version. See: https://github.com/google/or-tools/issues/3202

## Run Using Docker

You can run Maxfield using Docker for a consistent and isolated environment. Follow these steps:

### Build the Docker Image

1. Clone the repository:
   ```bash
   git clone https://github.com/tvwenger/maxfield.git
   cd maxfield
   ```

2. Build the Docker image:
   ```bash
   docker build -t maxfield .
   ```

### Run Maxfield with Docker

To run Maxfield, use the following command:

```bash
docker run --rm -v $(pwd):/app maxfield ./example/example_portals.txt --num_agents 3 --verbose --output_csv 
```

### Explanation of Command

- `docker run --rm`: Run the container and remove it after execution.
- `-v $(pwd):/app`: Mount the current working directory into the container at `/app` so that input and output files are accessible.
- `maxfield`: The name of the Docker image.
- `/app/example_portals.txt`: The input file containing the list of portals.
- `--num_agents 3 --verbose --output_csv`: Example arguments to customize the operation.

### Output Files

The results will be saved in the current working directory (`$(pwd)`), including:

- **`key_preparation.txt`**: List of keys needed for each portal.
- **`agent_assignments.txt`**: Link assignments for each agent.
- **`link_map.png`**: Visual representation of links and fields.
- **`plan_movie.gif`**: Step-by-step animation of the linking plan.

### Notes

Ensure the `example_portals.txt` file is present in your working directory or specify its actual location when running the command.

### Example

The `example` directory includes the Maxfield output for the portal
list in `example/example_portals.txt`. These results were generated
with the following command:

	maxfield-plan example_portals.txt --num_agents 3 --num_cpus 0 --verbose --output_csv --google_api_key <REDACTED> --google_api_secret <REDACTED>
	
Here was the output from this command:

```
Found 18 portals in portal file: example_portals.txt

Starting field generation with 8 CPUs.
Field generation runtime: 17.1 seconds.

==============================
Maxfield Plan Results:
    portals         = 18
    links           = 45
    fields          = 40
    max keys needed = 5
    AP from portals = 31500
    AP from links   = 14085
    AP from fields  = 50000
    TOTAL AP        = 95585
==============================

Optimizing agent link assignments.
Route optimization runtime: 24.5 seconds

Total plan build time: 16.6 minutes

Generating key preparation file.
File saved to: ./key_preparation.txt
CSV File saved to: ./key_preparation.csv
Generating ownership preparation file.
File saved to: ./ownership_preparation.txt
Generating agent key preparation file.
File saved to: ./agent_key_preparation.txt
CSV File saved to: ./agent_key_preparation.csv
Generating agent link assignments.
File saved to ./agent_assignments.txt
CSV File saved to ./agent_assignments.csv
Generating link assignment for agent 1.
File saved to ./agent_1_assignment.txt
Generating link assignment for agent 2.
File saved to ./agent_2_assignment.txt
Generating link assignment for agent 3.
File saved to ./agent_3_assignment.txt

Generating portal map.
File saved to: ./portal_map.png
Generating link map.
File saved to: ./link_map.png

Generating step-by-step plots.
Frames saved to: ./frames/
gifsicle: warning: huge GIF, conserving memory (processing may take a while)
GIF saved to ./plan_movie.gif

Total maxfield runtime: 87.5 seconds
```
	
### Usage

Get information about the maxfield parameters via `maxfield-plan --help`:

```
usage: maxfield.py [-h] [--version] [-n NUM_AGENTS]
                   [--num_field_iterations NUM_FIELD_ITERATIONS] [-c NUM_CPUS]
                   [--max_route_solutions MAX_ROUTE_SOLUTIONS]
                   [--max_route_runtime MAX_ROUTE_RUNTIME] [-o OUTDIR]
                   [--skip_plots] [--skip_step_plots] [-r]
                   [--google_api_key GOOGLE_API_KEY]
                   [--google_api_secret GOOGLE_API_SECRET] [--output_csv] [-v]
                   filename

Ingress Maxfield: An Ingress Linking and Fielding Strategy Generator.

positional arguments:
  filename              The properly formatted portal file.

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -n NUM_AGENTS, --num_agents NUM_AGENTS
                        The number of agents in the operation. (default: 1)
  --num_field_iterations NUM_FIELD_ITERATIONS
                        The number of random field plans to generate before
                        selecting the best. (default: 1000)
  -c NUM_CPUS, --num_cpus NUM_CPUS
                        The number of CPUs used to generate field plans. If
                        <1, use maximum. (default: 1)
  --max_route_solutions MAX_ROUTE_SOLUTIONS
                        The maximum number of agent routes to generate before
                        selecting the best. (default: 1000)
  --max_route_runtime MAX_ROUTE_RUNTIME
                        The maximum runtime of the agent routing algorithm in
                        seconds. (default: 60)
  -o OUTDIR, --outdir OUTDIR
                        The directory where results are saved. Created if
                        necessary. (default: .)
  --skip_plots          Skip generating plots. (default: False)
  --skip_step_plots     Skip generating step-by-step linking plots. (default:
                        False)
  -r, --res_colors      Use Resistance color scheme. (default: False)
  --google_api_key GOOGLE_API_KEY
                        A Google Maps API key. If set, make plots on top of
                        Google Maps background. (default: None)
  --google_api_secret GOOGLE_API_SECRET
                        A Google Maps API signature secret. If not set, do not
                        use signature. (default: None)
  --output_csv          Output machine-readable CSV files. (default: False)
  -v, --verbose         Print information along the way. (default: False)
```

### Portal list format

The input to Maxfield is a file containing a list of portals and parameters about
those portals. The portal file is semi-colon delimited, with the
following format:

	Portal 1 Name; Portal 1 Intel URL; (optional) Number of Keys in Hand; (optional) SBUL
	
The file must contain one line with this format for each portal.
The first item on each line must be a portal name, and it **must not** contain
a semi-colon. 

The second item must be the Intel URL for the portal,
which looks like:

	https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439
	
To obtain the Intel URL for a portal, navigate to the portal on the
Intel map, click on the portal to open the portal information frame,
then click on the "link" button at the top-left of the website. This will
open a pane with the portal URL, which contains the "pll=" bit. Simply
copy and paste this URL into your portal file.

Following the URL, there are two optional items which can appear in
any order or not at all. One is a number, which is interpreted as the
number of keys you already have in hand for this portal. The other is
the string SBUL which indicates that the portal is fully deployed with
SBULs, and thus the maximum number of out-going links is 40 instead of
the normal 8.

A correctly formatted line in the portal file will look like one of
these:

	Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439
	Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; 3
	Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; 3; SBUL
	Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; SBUL
	Catholic Church of the Holy Comforter; https://www.ingress.com/intel?ll=38.031745,-78.478592&z=18&pll=38.031796,-78.479439; SBUL; 3

### Output Files

	key_preparation.txt, key_preparation.csv
		List of portals, their numbers on the map, and how many keys are needed

	agent_key_preparation.txt, agent_key_preparation.csv
		How many keys each agent will need for each portal
		
	ownership_preparation.txt
		Which portals must be fully deployed pre-operation
		
	agent_assignments.txt, agent_assignments.csv
		The master list of the link order for all agents.
		
	agent_N_assignment.txt
		The subset of links made by agent N.
		
	portal_map.png
		A map showing the locations of the portals
		
	link_map.png
		A map showing the locations of portals and links
		
	frames/
	plan_movie.gif
		The directory contains images of each step of the plan, which
		are compiled into the GIF.
		The location of each agent is highlighted by the magenta box,
		new fields are in red, and the paths of the agents are the
		magenta dashed lines.
		
### Issues and Contributing

Anyone is welcome to submit issues or contribute to the development
of Maxfield via [Github](https://github.com/tvwenger/maxfield).

### License and Warranty

GNU Public License
http://www.gnu.org/licenses/

Maxfield is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Maxfield is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Maxfield. If not, see http://www.gnu.org/licenses/
