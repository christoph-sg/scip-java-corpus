{
  description = "Real-world corpus for testing scip-java's Kotlin and Java indexers";

  inputs = {
    flake-utils.url = "github:numtide/flake-utils";
    # Same channel and scip CLI as scip-java's own flake.
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    scip.url = "github:scip-code/scip";
  };

  outputs =
    {
      self,
      flake-utils,
      nixpkgs,
      scip,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfree = true;
            android_sdk.accept_license = true;
          };
        };

        # Corpus projects declare Gradle toolchains (e.g. kotlinx-datetime wants 8,
        # 11 and 17). bin/run.py hands these to Gradle as installation paths so
        # toolchains resolve to Nix JDKs instead of auto-downloads.
        toolchains = with pkgs; [
          jdk8
          jdk11
          jdk17
          jdk21
          jdk25
        ];

        # Read-only SDK: every platform and build-tools version the corpus needs
        # must be listed here, AGP cannot install missing ones.
        androidSdk =
          (pkgs.androidenv.composeAndroidPackages {
            platformVersions = [
              "36"
              "37.0"
            ];
            buildToolsVersions = [
              "36.0.0"
              "37.0.0"
            ];
          }).androidsdk;

        mkShell =
          { jdk, android }:
          pkgs.mkShellNoCC {
            packages = [
              jdk
              scip.packages.${system}.default
              pkgs.bash
              pkgs.git
              pkgs.python3
              pkgs.time
            ]
            ++ pkgs.lib.optional android androidSdk;
            JAVA_HOME = jdk.home;
            CORPUS_TOOLCHAINS = pkgs.lib.concatMapStringsSep "," (j: j.home) toolchains;
            shellHook = pkgs.lib.optionalString android ''
              export ANDROID_HOME=${androidSdk}/libexec/android-sdk
              export ANDROID_SDK_ROOT=$ANDROID_HOME
            '';
          };

        jdks = {
          jdk17 = pkgs.jdk17;
          jdk21 = pkgs.jdk21;
          jdk25 = pkgs.jdk25;
        };
      in
      {
        # One shell per corpus JDK, plus an -android variant with the SDK.
        devShells =
          pkgs.lib.mapAttrs (
            _: jdk:
            mkShell {
              inherit jdk;
              android = false;
            }
          ) jdks
          // pkgs.lib.mapAttrs' (
            name: jdk:
            pkgs.lib.nameValuePair "${name}-android" (mkShell {
              inherit jdk;
              android = true;
            })
          ) jdks
          // {
            default = mkShell {
              jdk = pkgs.jdk21;
              android = false;
            };
          };

        formatter = pkgs.nixfmt;
      }
    );
}
