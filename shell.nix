let
  unstable = import (fetchTarball "https://github.com/NixOS/nixpkgs/archive/nixos-unstable.tar.gz") {
    config.allowUnfree = true;
  };
  
  pkgs = unstable;
  cuda = pkgs.cudaPackages;

  llama-cpp-python-cuda = pkgs.python312Packages.llama-cpp-python.override {
    cudaSupport = true;
  };

in
pkgs.mkShell {
  name = "llama-cpp-python-env";

  buildInputs = [
    pkgs.python312
    pkgs.python312Packages.pip
    pkgs.python312Packages.virtualenv

    llama-cpp-python-cuda

    pkgs.stdenv.cc.cc.lib
    cuda.cuda_cudart
    cuda.libcublas
    cuda.libcusparse
    cuda.libcurand
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="/run/opengl-driver/lib:${pkgs.stdenv.cc.cc.lib}/lib:${cuda.cuda_cudart}/lib:${cuda.libcublas}/lib:${cuda.libcusparse}/lib:${cuda.libcurand}/lib:$LD_LIBRARY_PATH"

    echo "==========================================================="
    echo "llama-cpp-python (CUDA destekli) ortamı hazır."
    echo "==========================================================="

    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
  '';
}
