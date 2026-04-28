import React, { useState, useEffect } from 'react';

interface MCPConfig {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

interface MCPSelectorProps {
  mcpEnabled: boolean;
  mcpConfigs: MCPConfig[];
  onMCPChange: (enabled: boolean, configs: MCPConfig[]) => void;
}

const MCPSelector: React.FC<MCPSelectorProps> = ({
  mcpEnabled,
  mcpConfigs,
  onMCPChange,
}) => {
  const [enabled, setEnabled] = useState(mcpEnabled);
  const [configText, setConfigText] = useState(() => {
    // Initialize with the passed configs, handling empty array case
    if (Array.isArray(mcpConfigs) && mcpConfigs.length > 0) {
      return JSON.stringify(mcpConfigs, null, 2);
    }
    return '[]';
  });
  const [validationStatus, setValidationStatus] = useState<{
    isValid: boolean;
    message: string;
    serverCount?: number;
  }>({ isValid: true, message: 'JSON 有效 ✓' });
  const [showInfoModal, setShowInfoModal] = useState(false);

  useEffect(() => {
    validateConfig(configText);
  }, [configText]);

  // Sync with props when they change (for localStorage loading)
  useEffect(() => {
    setEnabled(mcpEnabled);
  }, [mcpEnabled]);

  useEffect(() => {
    if (Array.isArray(mcpConfigs)) {
      const newConfigText = mcpConfigs.length > 0 ? JSON.stringify(mcpConfigs, null, 2) : '[]';
      setConfigText(newConfigText);
    }
  }, [mcpConfigs]);

  const validateConfig = (text: string) => {
    if (!text.trim() || text.trim() === '[]') {
      setValidationStatus({ isValid: true, message: '当前为空配置' });
      return true;
    }

    try {
      const parsed = JSON.parse(text);

      if (!Array.isArray(parsed)) {
        throw new Error('配置必须是数组');
      }

      const errors: string[] = [];
      parsed.forEach((server: any, index: number) => {
        if (!server.name) {
          errors.push(`服务器 ${index + 1}：缺少 name`);
        }
        if (!server.command && !server.connection_url) {
          errors.push(`服务器 ${index + 1}：缺少 command 或 connection_url`);
        }
      });

      if (errors.length > 0) {
        throw new Error(errors.join('; '));
      }

      setValidationStatus({
        isValid: true,
        message: `JSON 有效 ✓（共 ${parsed.length} 个服务器）`,
        serverCount: parsed.length
      });
      return true;
    } catch (error: any) {
      setValidationStatus({
        isValid: false,
        message: `JSON 无效：${error.message}`
      });
      return false;
    }
  };

  const handleEnabledChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEnabled = e.target.checked;
    console.log('🔍 DEBUG: MCP enabled changed to:', newEnabled);
    setEnabled(newEnabled);

    if (newEnabled && validationStatus.isValid) {
      try {
        const configs = JSON.parse(configText || '[]');
        console.log('🔍 DEBUG: Calling onMCPChange with configs:', configs);
        onMCPChange(newEnabled, configs);
      } catch {
        console.log('🔍 DEBUG: JSON parse failed, calling with empty array');
        onMCPChange(newEnabled, []);
      }
    } else {
      console.log('🔍 DEBUG: Disabled or invalid, calling with empty array');
      onMCPChange(newEnabled, []);
    }
  };

  const handleConfigChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newText = e.target.value;
    console.log('🔍 DEBUG: Config text changed to:', newText);
    setConfigText(newText);

    if (enabled && validateConfig(newText)) {
      try {
        const configs = JSON.parse(newText || '[]');
        console.log('🔍 DEBUG: Parsed configs from textarea:', configs);
        console.log('🔍 DEBUG: Calling onMCPChange from textarea with:', { enabled, configs });
        onMCPChange(enabled, configs);
      } catch {
        console.log('🔍 DEBUG: JSON parse failed in textarea change');
        // Invalid JSON, don't update
      }
    }
  };

  const formatJSON = () => {
    try {
      const parsed = JSON.parse(configText || '[]');
      const formatted = JSON.stringify(parsed, null, 2);
      setConfigText(formatted);
    } catch {
      // Invalid JSON, don't format
    }
  };

  // Helper function to check if a preset is currently selected
  const isPresetSelected = (presetName: string): boolean => {
    try {
      const currentText = configText.trim();
      if (!currentText || currentText === '[]') return false;
      
      const parsed = JSON.parse(currentText);
      if (!Array.isArray(parsed)) return false;
      
      return parsed.some(server => server.name === presetName);
    } catch {
      return false;
    }
  };

  const togglePreset = (preset: string) => {
    console.log('🔍 DEBUG: togglePreset called with:', preset);
    console.log('🔍 DEBUG: Current configText:', configText);
    console.log('🔍 DEBUG: MCP enabled:', enabled);
    
    const presets: Record<string, MCPConfig> = {
      github: {
        name: 'github',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-github'],
        env: {
          GITHUB_PERSONAL_ACCESS_TOKEN: '你的_github_token'
        }
      },
      tavily: {
        name: 'tavily',
        command: 'npx',
        args: ['-y', 'tavily-mcp@0.1.2'],
        env: {
          TAVILY_API_KEY: '你的_tavily_api_key'
        }
      },
      filesystem: {
        name: 'filesystem',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-filesystem', '/path/to/allowed/directory'],
        env: {}
      }
    };

    const config = presets[preset];
    if (!config) {
      console.log('🔍 DEBUG: Preset config not found for:', preset);
      return;
    }

    try {
      let currentConfig: MCPConfig[] = [];
      const currentText = configText.trim();

      if (currentText && currentText !== '[]') {
        currentConfig = JSON.parse(currentText);
      }
      console.log('🔍 DEBUG: Current parsed config:', currentConfig);

      const existingIndex = currentConfig.findIndex(server => server.name === config.name);
      console.log('🔍 DEBUG: Existing index for', config.name, ':', existingIndex);

      if (existingIndex !== -1) {
        // Remove the preset if it exists (deselect)
        console.log('🔍 DEBUG: Removing preset');
        currentConfig.splice(existingIndex, 1);
      } else {
        // Add the preset if it doesn't exist (select)
        console.log('🔍 DEBUG: Adding preset');
        currentConfig.push(config);
      }

      const newText = JSON.stringify(currentConfig, null, 2);
      console.log('🔍 DEBUG: New config text:', newText);
      console.log('🔍 DEBUG: Final config array:', currentConfig);
      
      setConfigText(newText);
      
      // IMPORTANT: Also call onMCPChange immediately with the new config
      if (enabled) {
        console.log('🔍 DEBUG: Calling onMCPChange from togglePreset with:', { enabled, currentConfig });
        onMCPChange(enabled, currentConfig);
      }
      
    } catch (error) {
      console.error('🔍 DEBUG: Error toggling preset:', error);
    }
  };

  const showExample = () => {
    const exampleConfig = [
      {
        name: 'github',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-github'],
        env: {
          GITHUB_PERSONAL_ACCESS_TOKEN: '你的_github_token'
        }
      },
      {
        name: 'filesystem',
        command: 'npx',
        args: ['-y', '@modelcontextprotocol/server-filesystem', '/path/to/allowed/directory'],
        env: {}
      }
    ];

    setConfigText(JSON.stringify(exampleConfig, null, 2));
  };

  return (
    <div className="form-group">
      <div className="settings mcp-section">
        <div className="settings mcp-header">
          <label className="agent_question">
            <input
              type="checkbox"
              className="settings mcp-toggle"
              checked={enabled}
              onChange={handleEnabledChange}
            />
            启用 MCP（模型上下文协议）
          </label>
          <button
            type="button"
            className="settings mcp-info-btn"
            onClick={() => setShowInfoModal(true)}
            title="了解 MCP"
          >
            ℹ️
          </button>
        </div>
        <small className="text-muted" style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.85rem', marginBottom: '15px', display: 'block' }}>
          通过 MCP 服务器连接外部工具和数据源
        </small>

        {enabled && (
          <div className="settings mcp-config-section">
            <div className="settings mcp-presets">
              <label className="agent_question" style={{ marginBottom: '10px' }}>快速预设</label>
              <div className="settings preset-buttons">
                <button
                  type="button"
                  className={`settings preset-btn ${isPresetSelected('github') ? 'selected' : ''}`}
                  onClick={() => togglePreset('github')}
                >
                  <i className="fab fa-github"></i> GitHub
                </button>
                <button
                  type="button"
                  className={`settings preset-btn ${isPresetSelected('tavily') ? 'selected' : ''}`}
                  onClick={() => togglePreset('tavily')}
                >
                  <i className="fas fa-search"></i> Tavily 网页搜索
                </button>
                <button
                  type="button"
                  className={`settings preset-btn ${isPresetSelected('filesystem') ? 'selected' : ''}`}
                  onClick={() => togglePreset('filesystem')}
                >
                  <i className="fas fa-folder"></i> 本地文件
                </button>
              </div>
              <small className="text-muted" style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.85rem', marginTop: '8px', display: 'block' }}>
                点击预设可在下方配置中启用或移除对应的 MCP 服务器，已选项会高亮显示。
              </small>
            </div>

            <div className="settings mcp-config-group">
              <label className="agent_question" style={{ marginBottom: '10px' }}>MCP 服务器配置</label>
              <textarea
                className={`settings mcp-config-textarea ${validationStatus.isValid ? 'valid' : 'invalid'}`}
                rows={12}
                placeholder="将 MCP 服务器配置以 JSON 数组形式粘贴到这里..."
                value={configText}
                onChange={handleConfigChange}
                style={{ minHeight: '300px' }}
              />
              <div className="settings mcp-config-status">
                <span className={`settings mcp-status-text ${validationStatus.isValid ? 'valid' : 'invalid'}`}>
                  {validationStatus.message}
                </span>
                <button
                  type="button"
                  className="settings mcp-format-btn"
                  onClick={formatJSON}
                >
                  <i className="fas fa-code"></i> 格式化 JSON
                </button>
              </div>
              <small className="text-muted" style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '0.85rem', marginTop: '8px', display: 'block', lineHeight: '1.4' }}>
                请以 JSON 数组形式粘贴 MCP 服务器配置。每个服务器对象通常需要包含{' '}
                <code style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: '3px', color: '#0d9488' }}>name</code>,{' '}
                <code style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: '3px', color: '#0d9488' }}>command</code>,{' '}
                <code style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: '3px', color: '#0d9488' }}>args</code>，以及可选的{' '}
                <code style={{ backgroundColor: 'rgba(255, 255, 255, 0.1)', padding: '2px 4px', borderRadius: '3px', color: '#0d9488' }}>env</code> 环境变量。{' '}
                <a
                  href="#"
                  className="settings mcp-example-link"
                  onClick={(e) => { e.preventDefault(); showExample(); }}
                  style={{ color: '#0d9488', textDecoration: 'none', fontWeight: '500' }}
                >
                  查看示例 →
                </a>
              </small>
            </div>
          </div>
        )}

        {/* MCP Info Modal */}
        {showInfoModal && (
          <div className="settings mcp-info-modal visible">
            <div className="settings mcp-info-content">
              <button
                className="settings mcp-info-close"
                onClick={() => setShowInfoModal(false)}
              >
                <i className="fas fa-times"></i>
              </button>
              <h3>模型上下文协议（MCP）</h3>
              <p>MCP 让 GPT Researcher 可以通过统一协议连接外部工具和数据源。</p>

              <h4 className="highlight">价值：</h4>
              <ul>
                <li><span className="highlight">访问本地数据：</span>连接数据库、文件系统和 API</li>
                <li><span className="highlight">调用外部工具：</span>集成网页服务和第三方工具</li>
                <li><span className="highlight">扩展能力：</span>通过 MCP 服务器增加自定义功能</li>
                <li><span className="highlight">保持安全：</span>结合鉴权机制进行受控访问</li>
              </ul>

              <h4 className="highlight">快速开始：</h4>
              <ul>
                <li>先勾选上方开关启用 MCP</li>
                <li>点击预设，把常用服务器快速加入 JSON</li>
                <li>或者直接粘贴你自己的 MCP JSON 配置</li>
                <li>启动研究后，系统会按当前配置调用 MCP</li>
              </ul>

              <h4 className="highlight">配置格式：</h4>
              <p>每个 MCP 服务器通常都是一个 JSON 对象，包含以下字段：</p>
              <ul>
                <li><span className="highlight">name：</span>唯一标识，例如 &quot;github&quot;、&quot;filesystem&quot;</li>
                <li><span className="highlight">command：</span>启动服务器的命令，例如 &quot;npx&quot;、&quot;python&quot;</li>
                <li><span className="highlight">args：</span>命令参数数组，例如 [&quot;-y&quot;, &quot;@modelcontextprotocol/server-github&quot;]</li>
                <li><span className="highlight">env：</span>环境变量对象，例如 {JSON.stringify({API_KEY: "your_key"})}</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MCPSelector;
