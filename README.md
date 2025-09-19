# Elsa Apps

This repository provides official application projects for running [Elsa Workflows](https://github.com/elsa-workflows/elsa-core) and [Elsa Studio](https://github.com/elsa-workflows/elsa-studio) as configurable ASP.NET Core applications.  

Each project comes with its own `Dockerfile`, enabling you to run Elsa servers and studios as prebuilt, containerized applications.

## Projects

1. **Elsa Server**  
   An ASP.NET Core project representing a configurable Elsa Workflow Server application.

2. **Elsa Studio (Blazor WASM)**  
   An ASP.NET Core Blazor project representing a configurable Elsa Studio (WASM) application.

3. **Elsa Studio (Blazor Server)**  
   An ASP.NET Core Blazor project representing a configurable Elsa Studio (Blazor Server) application.

4. **Elsa Server + Studio (Blazor WASM)**  
   An ASP.NET Core project hosting both the Elsa Workflow Server and the Elsa Studio UI (WASM).

5. **Elsa Server + Studio (Blazor Server)**  
   An ASP.NET Core project hosting both the Elsa Workflow Server and the Elsa Studio UI (Blazor Server).

## Goal

The long-term goal is to evolve these projects into fully configurable Docker images.  
This will allow users to run Elsa Workflow Servers and Elsa Studio apps as prebuilt applications, configurable through:

- **Environment variables**  
- **Configuration files** (via mounts)

## Getting Started

Each project includes a `Dockerfile`. You can build and run them as follows:

```bash
# Example: build and run the Elsa Server image
docker build -t elsa-server ./src/Elsa.Server
docker run -d -p 5000:80 --name elsa-server elsa-server
````

## License

[MIT](LICENSE)
