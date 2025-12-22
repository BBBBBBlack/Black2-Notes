## 静态注册

Pass 被设计为 LLVM 源代码的一部分，直接修改 LLVM 的内部文件

`Pass` 被编译进 `opt` 可执行文件中

* Pass代码（llvm-project-17.0.6.src/llvm/lib/Transform/Utils）

  ```c++
  #include "llvm/Transforms/Utils/HelloWorld.h"
  
  using namespace llvm;
  
  PreservedAnalyses HelloWorldPass::run(Function &F,
                                        FunctionAnalysisManager &AM) {
    errs() << F.getName() << "\n";
    return PreservedAnalyses::all();
  }
  ```

* CMakeLists.txt
  ```
  add_llvm_component_library(LLVMTransformUtils
  ……
  HelloWorld.cpp
  ……)
  ```

* 父目录CMakeLists.txt

  ```
  add_subdirectory(HelloWorld)
  ```

* 修改 `llvm/lib/Passes/PassRegistry.def`

  ```
  FUNCTION_PASS("helloworld", HelloWorldPass())
  ```

* 运行命令
  ```
  opt -disable-output a.ll -passes=helloworld
  ```

## 注册为插件

Pass 被设计为外部插件（`.so` 文件）

`opt` 可执行文件不认识Pass，必须在运行时使用 `-load-pass-plugin=xxx.so` 来加载这个插件

* Pass代码（llvm-project-17.0.6.src/llvm/examples/Bye）
  ```c++
  static cl::opt<bool> Wave("wave-goodbye", cl::init(false),
                            cl::desc("wave good bye"));
  namespace {
  
  bool runBye(Function &F) {
    if (Wave) {
      errs() << "Bye: ";
      errs().write_escaped(F.getName()) << '\n';
    }
    return false;
  }
  
  struct Bye : PassInfoMixin<Bye> {
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &) {
      if (!runBye(F))
        return PreservedAnalyses::all();
      return PreservedAnalyses::none();
    }
  };
  
  } // namespace
  
  char LegacyBye::ID = 0;
  
  /* New PM Registration */
  llvm::PassPluginLibraryInfo getByePluginInfo() {
    return {LLVM_PLUGIN_API_VERSION, "Bye", LLVM_VERSION_STRING,
            // 传入一个 PassBuilder (PB) 对象
            [](PassBuilder &PB) {
              // 在运行向量化优化之前自动插入
              PB.registerVectorizerStartEPCallback(
                  [](llvm::FunctionPassManager &PM, OptimizationLevel Level) {
                    PM.addPass(Bye());
                  });
              // 响应命令行
              PB.registerPipelineParsingCallback(
                  [](StringRef Name, llvm::FunctionPassManager &PM,
                     ArrayRef<llvm::PassBuilder::PipelineElement>) {
                    if (Name == "goodbye") {
                      PM.addPass(Bye());
                      return true;
                    }
                    return false;
                  });
            }};
  }
  
  #ifndef LLVM_BYE_LINK_INTO_TOOLS
  /* opt 工具在使用 -load-pass-plugin 加载 .so 文件时，会主动寻找的标准 C 函数名 */
  extern "C" LLVM_ATTRIBUTE_WEAK ::llvm::PassPluginLibraryInfo
  llvmGetPassPluginInfo() {
    return getByePluginInfo();
  }
  #endif
  ```

* CMakeLists.txt
  ```makefile
  add_llvm_pass_plugin(Bye
      Bye.cpp
      DEPENDS
      intrinsics_gen
      BUILDTREE_ONLY
  )
  ```

* 父目录CMakeLists.txt
  ```
  add_subdirectory(Bye)
  ```

* 运行命令

  ```
  opt -load-pass-plugin=llvm-project-17.0.6.src/build/lib/Bye.so --wave-goodbye
  ```

  