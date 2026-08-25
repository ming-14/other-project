package main

// globMatch 简单通配符匹配:支持 * (任意字符序列,含空)与 ? (单个字符)。
// 模型名通常很短,递归实现足够;不依赖 path.Match 是因为 * 在 path.Match 中
// 不匹配路径分隔符,而模型名可能含 / (如 org/model)。
func globMatch(pattern, name string) bool {
	if pattern == "" {
		return name == ""
	}
	switch pattern[0] {
	case '*':
		// 匹配 0 个或多个字符:尝试所有切分点
		for i := 0; i <= len(name); i++ {
			if globMatch(pattern[1:], name[i:]) {
				return true
			}
		}
		return false
	case '?':
		return len(name) > 0 && globMatch(pattern[1:], name[1:])
	default:
		return len(name) > 0 && pattern[0] == name[0] && globMatch(pattern[1:], name[1:])
	}
}

// matchesModel 判断该上游是否负责指定模型。
// 未配置 models(或配置了 *)= 匹配所有;请求 model 为空时不过滤(交给上游拒绝)。
func (u *Upstream) matchesModel(model string) bool {
	if model == "" || len(u.models) == 0 {
		return true
	}
	for _, p := range u.models {
		if p == "*" || globMatch(p, model) {
			return true
		}
	}
	return false
}
