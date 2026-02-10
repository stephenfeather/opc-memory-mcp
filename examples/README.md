# Examples

## opc.json.example

Config file for persistent OPC directory configuration.

**Installation:**
```bash
cp opc.json.example ~/.claude/opc.json
# Edit to set your actual OPC path
```

## hooks/opc-path.ts

Shared TypeScript module for OPC directory resolution in Claude Code hooks.

**Installation:**
```bash
mkdir -p ~/.claude/hooks/src/shared
cp hooks/opc-path.ts ~/.claude/hooks/src/shared/
```

**Usage in your hooks:**
```typescript
import { getOpcDir, requireOpcDir, hasOpcDir } from './shared/opc-path';

// Get OPC dir or null
const opcDir = getOpcDir();

// Get OPC dir or exit gracefully (for hooks that require OPC)
const opcDir = requireOpcDir();

// Check if OPC is available
if (hasOpcDir()) {
  // OPC-specific logic
}
```

**After adding/modifying hooks:**
```bash
cd ~/.claude/hooks && npm run build
```
