"The attempts on a concept page: code keeps its lines, no slot such as {x1} shows, and the same question asked again is one row."

def test_attempts_keep_code_hide_slots_and_fold_repeats(mk, lr):
    "Code in a question keeps its lines, an old question with slots shows only its filled sentences, and three answers to one question are one row with a fold."
    code = 'Read this code:\n\ndef neuron(w, x, b):\n    s = 0\n    for i in range(len(w)):\n        s += w[i] * x[i]\n    return s + b\n\nWhat does it compute?'
    for k in range(3): lr.record('ranking', code, f'the weighted sum {k}', '', k == 2, 70, 2)
    lr.record('ranking', 'For x = (2, 3), b = 0.5: Inputs are {x1}, {x2}. Bias is {b}. What is z?', '7.5', '', True, 70, 2)
    t = mk().get('/c/ranking').text
    assert '<code' in t and '    s = 0\n    for i in range(len(w)):' in t   # the code is in a block, with its lines and its indent
    assert '{x1}' not in t and '{b}' not in t and 'For x = (2, 3), b = 0.5: What is z?' in t
    assert t.count('What does it compute?') == 1 and '2 earlier answers' in t and 'the weighted sum 0' in t
