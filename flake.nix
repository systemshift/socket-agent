{
  description = "Socket Agent - Minimal API discovery for LLM agents";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          # Core dependencies from pyproject.toml
          fastapi
          pydantic
          
          # Additional dependencies found in Python files
          httpx
          uvicorn
          
          # Development/testing dependencies
          pytest
          pytest-asyncio
          
          # Development tools from pyproject.toml
          black
          isort
          python-dotenv
          
          # Add pip for editable installs
          pip
          
          # Interactive Python shell
          ipython
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            pythonEnv
            # Additional development tools
            git
          ];
          
          shellHook = ''
            echo "Socket Agent development environment activated"
            echo "Python version: $(python --version)"
            
            # Set up Python path for local development
            export PYTHONPATH="${toString ./.}/socket_agent:${toString ./.}/socket_agent_client:$PYTHONPATH"
            echo "Added local packages to PYTHONPATH"
            
            echo ""
            echo "Available packages:"
            echo "  - fastapi"
            echo "  - pydantic" 
            echo "  - httpx"
            echo "  - uvicorn"
            echo "  - pytest"
            echo "  - black"
            echo "  - isort"
            echo "  - python-dotenv"
            echo "  - ipython"
            echo "  - socket_agent (via PYTHONPATH)"
            echo "  - socket_agent_client (via PYTHONPATH)"
            echo ""
            echo "To run the examples:"
            echo "  cd examples/benchmark"
            echo "  python -m uvicorn banking_api.main:app --reload --port 8001"
            echo "  python -m uvicorn grocery_api.main:app --reload --port 8002"
            echo "  python -m uvicorn recipe_api.main:app --reload --port 8003"
            echo ""
            echo "To run tests:"
            echo "  pytest"
          '';
        };

        packages.default = pkgs.python311Packages.buildPythonPackage {
          pname = "socket-agent";
          version = "0.1.0";
          
          src = ./.;
          
          format = "pyproject";
          
          nativeBuildInputs = with pkgs.python311Packages; [
            setuptools
            wheel
          ];
          
          propagatedBuildInputs = with pkgs.python311Packages; [
            fastapi
            pydantic
            httpx
            uvicorn
          ];
          
          checkInputs = with pkgs.python311Packages; [
            pytest
            pytest-asyncio
          ];
          
          pythonImportsCheck = [
            "socket_agent"
          ];
          
          meta = with pkgs.lib; {
            description = "Minimal API discovery for LLM agents";
            license = licenses.mit;
            maintainers = [ ];
          };
        };
      });
}
