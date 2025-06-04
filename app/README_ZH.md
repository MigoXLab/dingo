# dingo

dingo 是一个基于 Electron 和 React 的桌面应用程序，用于可视化数据评测result。提供可同时支持build spa应用web应用，也支持build 桌面应用。

## 推荐的 IDE 设置

- [VSCode](https://code.visualstudio.com/) + [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint) + [Prettier](https://marketplace.visualstudio.com/items?itemName=esbenp.prettier-vscode)

## 项目设置

### 安装

```bash
$ npm install
```

### 开发

```bash
$ npm run dev
```

### 构建

```bash
# 针对 Windows
$ npm run build:win

# 针对 macOS
$ npm run build:mac

# 构建 macOS 版本（x64 架构）
$ npm run build:mac-x64

# 针对 Linux
$ npm run build:linux

```

### 使用 Dingo CLI 启动可视化web

```bash
# 技术方案：build:web ---> web-static/index.html --> 执行cli --> 可视化web
npm run buid:web
在保证dingo的依赖安装完毕后，回到dingo根目录，若根目录有build产物，则可以不依赖node
$ python -m dingo.run.vsl  --input /path/to/your/input/directory #拉起web

在安装node环境的前提下，执行
$ npm run dev
python -m dingo.run.vsl  --input /path/to/your/input/directory  --mode app #拉起dingo app
```

### CLI可视化web 与 Dingo桌面应用的对比

```bash
CLI可视化web: 默认执行cli的时候一次性注入数据，不支持更换本地目录，需cli重新执行
Dingo桌面应用: 默认不注入数据，支持添加&更换本地目录，支持数据可视化
```

### 开发脚本

```bash
# 格式化代码
$ npm run format

# 代码检查
$ npm run lint

# 类型检查
$ npm run typecheck

# 启动应用程序（预览模式）
$ npm run dev
```

此命令以预览模式运行应用程序。它使用 electron-vite 启动 Electron 应用程序，使用已构建的文件，允许您像在生产环境中一样测试应用程序，但无需打包。

```bash
# 构建 Web 版本
$ npm run build:web
```

此命令为 Web 部署构建应用程序。它使用 electron-vite 构建项目，但配置专门针对 Web 输出进行了调整。这允许您将 Electron 应用程序部署为 Web 应用程序，这在创建桌面应用程序的 Web 版本时非常有用。

```bash
# 提供 Web 构建服务
$ npm run serve:web

# 构建并解包
$ npm run build:unpack

```

### 其他有用的命令

```bash
# 使用 npx 启动
$ npm run start-npx

# 运行 postinstall 脚本
$ npm run postinstall
```
